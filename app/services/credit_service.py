"""Every generated image costs one credit; all mutations use one SQLite transaction."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4
from fastapi import HTTPException
from app.models.db import get_connection

CHINA = timezone(timedelta(hours=8))
WELCOME_CREDITS = 5
DAILY_CHECKIN_CREDITS = 2


def now():
    return int(time.time())


def day(timestamp=None):
    return datetime.fromtimestamp(now() if timestamp is None else timestamp, CHINA).date().isoformat()


def grant(con, user_id, source, reference, amount, expires_at=None):
    con.execute('INSERT OR IGNORE INTO credit_grants VALUES (?,?,?,?,?,?,?,?)',
                (uuid4().hex,user_id,source,reference,amount,amount,expires_at,now()))


def ensure_wallet(con, user_id):
    if not con.execute("SELECT 1 FROM credit_grants WHERE user_id=? AND source='welcome'",(user_id,)).fetchone():
        # Existing grants stay unchanged; uninitialized wallets count prior successful images.
        used=con.execute("SELECT COUNT(*) FROM generations WHERE user=? AND status='completed'",(user_id,)).fetchone()[0]
        grant(con,user_id,'welcome','registration',max(0,WELCOME_CREDITS-used))


def summary(user_id):
    timestamp=now()
    with closing(get_connection()) as con, con:
        con.execute('BEGIN IMMEDIATE')
        ensure_wallet(con,user_id)
        free,paid=con.execute('''SELECT COALESCE(SUM(CASE WHEN source!='membership' THEN remaining ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN source='membership' THEN remaining ELSE 0 END),0)
            FROM credit_grants WHERE user_id=? AND (expires_at IS NULL OR expires_at>?)''',(user_id,timestamp)).fetchone()
        checked=bool(con.execute("SELECT 1 FROM credit_grants WHERE user_id=? AND source='checkin' AND reference=?",(user_id,day(timestamp))).fetchone())
        member=con.execute('SELECT * FROM memberships WHERE user_id=?',(user_id,)).fetchone()
        held=con.execute("SELECT COUNT(*) FROM credit_holds WHERE user_id=? AND state='reserved'",(user_id,)).fetchone()[0]
    return {'available':free+paid,'free_credits':free,'membership_credits':paid,'reserved':held,
            'checked_in_today':checked,'checkin_reward':DAILY_CHECKIN_CREDITS,'checkin_date':day(timestamp),'timezone':'Asia/Shanghai',
            'membership': {'active':member['expires_at']>timestamp,'plan_id':member['plan_id'],'expires_at':member['expires_at']} if member else None}


def checkin(user_id):
    with closing(get_connection()) as con, con:
        con.execute('BEGIN IMMEDIATE')
        ensure_wallet(con,user_id)
        before=con.total_changes
        grant(con,user_id,'checkin',day(),DAILY_CHECKIN_CREDITS)
        awarded=con.total_changes>before
    return {'awarded':DAILY_CHECKIN_CREDITS if awarded else 0, **summary(user_id)}


def reserve_credit(con, user_id, generation_id):
    ensure_wallet(con,user_id)
    row=con.execute('''SELECT grant_id FROM credit_grants WHERE user_id=? AND remaining>0
        AND (expires_at IS NULL OR expires_at>?)
        ORDER BY expires_at IS NULL, expires_at, created_at, grant_id LIMIT 1''',(user_id,now())).fetchone()
    if not row:
        raise HTTPException(402, '生成额度不足，请每日签到获取额度后再试')
    con.execute('UPDATE credit_grants SET remaining=remaining-1 WHERE grant_id=? AND remaining>0',(row['grant_id'],))
    con.execute('INSERT INTO credit_holds VALUES (?,?,?,?,0,?)',(generation_id,user_id,row['grant_id'],'reserved',now()))


def mark_submitted(generation_id):
    with closing(get_connection()) as con, con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT status FROM generations WHERE generation_id=?',(generation_id,)).fetchone()
        if not row or row['status']!='pending':
            return False
        con.execute("UPDATE credit_holds SET submitted=1 WHERE generation_id=? AND state='reserved'",(generation_id,))
    return True


def settle(con,generation_id,status):
    row=con.execute('SELECT * FROM credit_holds WHERE generation_id=?',(generation_id,)).fetchone()
    if not row or row['state']!='reserved':
        return
    refund=status=='failed' or (status=='cancelled' and not row['submitted'])
    if refund:
        # A refunded expired membership grant remains expired; it never becomes free credit.
        con.execute('UPDATE credit_grants SET remaining=remaining+1 WHERE grant_id=?',(row['grant_id'],))
    con.execute('UPDATE credit_holds SET state=? WHERE generation_id=?',('refunded' if refund else 'consumed',generation_id))
