from calendar import monthrange
import hashlib
import json
import os
from contextlib import closing
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from fastapi import HTTPException
from app.models.db import get_connection
from app.services.credit_service import CHINA, now, ensure_wallet, grant

PRICE_PER_CREDIT_FEN = 100
MIN_CREDITS = 1
MAX_CREDITS = 10000


def _configured_redemptions():
    """Read redemption definitions only from the server environment.

    MHP_REDEMPTION_CODES is a JSON array of {code, credits}. Plain
    codes never reach a response, database row, browser bundle, or source control.
    """
    raw = os.environ.get('MHP_REDEMPTION_CODES', '').strip()
    if not raw:
        return {}
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    values = {}
    if not isinstance(entries, list):
        return values
    for item in entries:
        if not isinstance(item, dict):
            continue
        code = str(item.get('code', '')).strip().upper()
        credits = item.get('credits')
        if 8 <= len(code) <= 64 and isinstance(credits, int) and 1 <= credits <= MAX_CREDITS:
            values[hashlib.sha256(code.encode()).hexdigest()] = {'credits': credits}
    return values


def redeem(user_id, code):
    normalized = code.strip().upper()
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    offer = _configured_redemptions().get(digest)
    if not offer:
        raise HTTPException(400, '兑换码无效、未启用或已过期')
    with closing(get_connection()) as con, con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM redemption_claims WHERE code_hash=?', (digest,)).fetchone():
            raise HTTPException(409, '该兑换码已被使用')
        grant(con, user_id, 'redemption', digest, offer['credits'])
        con.execute('INSERT INTO redemption_claims (code_hash,user_id,credits,months,days,claimed_at) VALUES (?,?,?,?,?,?)',
                    (digest, user_id, offer['credits'], 0, 0, now()))
    return {'credits': offer['credits']}


def add_duration(timestamp, days, months):
    if days:
        return timestamp+days*86400
    date=datetime.fromtimestamp(timestamp,CHINA)
    index=date.year*12+date.month-1+months
    year,month=index//12,index%12+1
    return int(date.replace(year=year,month=month,day=min(date.day,monthrange(year,month)[1])).timestamp())


def public_order(row):
    return {k:row[k] for k in ('order_id','plan_id','price_fen','credits','status','created_at','payment_deadline','paid_at','membership_expires_at')}


def get_order(user_id,order_id):
    with closing(get_connection()) as con:
        row=con.execute('SELECT * FROM membership_orders WHERE order_id=? AND user_id=?',(order_id,user_id)).fetchone()
    if not row:
        raise HTTPException(404,'订单不存在')
    return public_order(row)


def list_orders(user_id):
    with closing(get_connection()) as con:
        rows=con.execute('SELECT * FROM membership_orders WHERE user_id=? ORDER BY created_at DESC,order_id DESC LIMIT 30',(user_id,)).fetchall()
    return [public_order(row) for row in rows]


def create_order(user_id,credits,request_key,app_id,seller_id):
    if not isinstance(credits,int) or isinstance(credits,bool) or not MIN_CREDITS <= credits <= MAX_CREDITS:
        raise HTTPException(400,f'充值数量须为{MIN_CREDITS}至{MAX_CREDITS}张')
    with closing(get_connection()) as con, con:
        con.execute('BEGIN IMMEDIATE')
        existing=con.execute('SELECT * FROM membership_orders WHERE user_id=? AND request_key=?',(user_id,request_key)).fetchone()
        if existing:
            if existing['plan_id']!='credits' or existing['credits']!=credits:
                raise HTTPException(409,'同一充值请求不能更改数量')
            return dict(existing)
        # Repeated clicks/new browser tabs reuse an unpaid recharge for the same quantity.
        existing=con.execute("SELECT * FROM membership_orders WHERE user_id=? AND plan_id='credits' AND credits=? AND status='pending' AND payment_deadline>? ORDER BY created_at DESC LIMIT 1",(user_id,credits,now())).fetchone()
        if existing:
            return dict(existing)
        timestamp=now()
        order_id=uuid4().hex
        con.execute('''INSERT INTO membership_orders
            (order_id,user_id,request_key,plan_id,price_fen,credits,days,months,status,app_id,seller_id,created_at,payment_deadline)
            VALUES (?,?,?,?,?,?,?,?,'pending',?,?,?,?)''',
            (order_id,user_id,request_key,'credits',credits*PRICE_PER_CREDIT_FEN,credits,0,0,app_id,seller_id,timestamp,timestamp+1800))
        return dict(con.execute('SELECT * FROM membership_orders WHERE order_id=?',(order_id,)).fetchone())


def apply_verified_payment(payload):
    """Call only after RSA2 verification and configured app/seller verification."""
    order_id,trade_no=payload.get('out_trade_no',''),payload.get('trade_no','')
    try:
        amount=Decimal(payload.get('total_amount',''))*100
        if not amount.is_finite() or amount!=amount.to_integral_value():
            raise ValueError('invalid amount')
    except (InvalidOperation,ValueError,TypeError):
        raise HTTPException(400,'支付金额无效') from None
    with closing(get_connection()) as con, con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM membership_orders WHERE order_id=?',(order_id,)).fetchone()
        if not row or row['plan_id']!='credits' or amount!=row['price_fen'] or payload.get('app_id')!=row['app_id'] or payload.get('seller_id')!=row['seller_id']:
            raise HTTPException(400,'支付通知与订单不匹配')
        status=payload.get('trade_status')
        if status not in ('TRADE_SUCCESS','TRADE_FINISHED'):
            if status=='TRADE_CLOSED':
                if row['status']=='paid' and trade_no!=row['trade_no']:
                    raise HTTPException(400,'交易编号不匹配')
                elif row['status']=='pending':
                    con.execute("UPDATE membership_orders SET status='closed' WHERE order_id=?",(order_id,))
            return
        if not trade_no or len(trade_no)>128:
            raise HTTPException(400,'交易编号无效')
        if row['status']=='paid':
            if row['trade_no']!=trade_no:
                raise HTTPException(400,'交易编号不匹配')
            return
        if row['status']!='pending':
            raise HTTPException(409,'订单状态异常，请人工核对')
        if con.execute('SELECT 1 FROM membership_orders WHERE trade_no=?',(trade_no,)).fetchone():
            raise HTTPException(400,'交易编号重复')
        timestamp=now()
        ensure_wallet(con,row['user_id'])
        grant(con,row['user_id'],'recharge',order_id,row['credits'])
        con.execute("UPDATE membership_orders SET status='paid',paid_at=?,trade_no=? WHERE order_id=?",(timestamp,trade_no,order_id))


def _revoke_refunded_order(con,order):
    """Reflect a signed full-refund notification; this function never issues a refund."""
    from app.services.credit_service import settle
    timestamp=now()
    con.execute("UPDATE membership_orders SET status='refunded' WHERE order_id=?",(order['order_id'],))
    holds=con.execute('''SELECT h.generation_id FROM credit_holds h JOIN credit_grants c ON h.grant_id=c.grant_id
        WHERE c.user_id=? AND c.source='membership' AND c.reference=? AND h.state='reserved' ''',(order['user_id'],order['order_id'])).fetchall()
    for hold in holds:
        con.execute("UPDATE generations SET status='cancelled',error='会员订单已退款，任务已取消' WHERE generation_id=? AND status='pending'",(hold['generation_id'],))
        settle(con,hold['generation_id'],'cancelled')
    con.execute("UPDATE credit_grants SET remaining=0,expires_at=? WHERE user_id=? AND source='membership' AND reference=?",(timestamp,order['user_id'],order['order_id']))
    paid=con.execute("SELECT * FROM membership_orders WHERE user_id=? AND status='paid' ORDER BY membership_expires_at,order_id",(order['user_id'],)).fetchall()
    expiry=0
    for row in paid:
        expiry=add_duration(max(expiry,row['paid_at']),row['days'],row['months'])
    expiry=expiry if paid else timestamp
    plan_id=paid[-1]['plan_id'] if paid else order['plan_id']
    con.execute('UPDATE memberships SET plan_id=?,expires_at=?,updated_at=? WHERE user_id=?',(plan_id,expiry,timestamp,order['user_id']))
    con.execute("UPDATE credit_grants SET expires_at=? WHERE user_id=? AND source='membership' AND expires_at>?",(expiry,order['user_id'],timestamp))
    con.execute("UPDATE membership_reminders SET state='superseded' WHERE user_id=? AND state IN ('pending','failed')",(order['user_id'],))
    if expiry>timestamp and paid:
        lead=6*3600 if paid[-1]['days'] else 3*86400
        con.execute('''INSERT INTO membership_reminders (reminder_id,user_id,expires_at,due_at) VALUES (?,?,?,?)
            ON CONFLICT(user_id,expires_at) DO UPDATE SET state='pending',due_at=excluded.due_at
            WHERE membership_reminders.state='superseded' ''',(uuid4().hex,order['user_id'],expiry,expiry-lead))
