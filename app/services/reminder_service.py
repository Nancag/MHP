"""Durable reminder outbox. No browser/API call is required to trigger delivery."""
from contextlib import closing
import logging
import os
from uuid import uuid4
from app.models.db import get_connection
from app.services import auth_service as mail
from app.services.credit_service import now

logger=logging.getLogger(__name__)


def process_due(limit=2):
    if os.environ.get('MEMBERSHIP_REMINDERS_ENABLED','1')!='1' or not mail.email_ready():
        return 0
    sent=0
    for _ in range(limit):
        timestamp=now()
        with closing(get_connection()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            # Crashed senders must not blindly resend a message whose SMTP result is unknown.
            con.execute("UPDATE membership_reminders SET state='uncertain' WHERE state='sending' AND last_attempt<?",(timestamp-600,))
            row=con.execute('''SELECT r.*,u.email FROM membership_reminders r JOIN memberships m ON m.user_id=r.user_id
                JOIN users u ON u.user_id=r.user_id WHERE r.expires_at=m.expires_at AND r.expires_at>?
                AND r.due_at<=? AND r.state IN ('pending','failed') AND r.attempts<3
                AND (r.last_attempt IS NULL OR r.last_attempt<=?) ORDER BY r.expires_at LIMIT 1''',(timestamp,timestamp,timestamp-3600)).fetchone()
            if not row:
                break
            start=timestamp-timestamp%86400
            attempts=con.execute('SELECT COUNT(*) FROM membership_email_attempts WHERE created_at>=?',(start,)).fetchone()[0]
            total=attempts+con.execute('SELECT COUNT(*) FROM auth_codes WHERE created_at>=?',(start,)).fetchone()[0]
            smtp=mail.email_provider()=='netease_smtp'
            if attempts>=(2 if smtp else 10) or total>=(10 if smtp else 90):
                break
            con.execute("UPDATE membership_reminders SET state='sending',attempts=attempts+1,last_attempt=? WHERE reminder_id=?",(timestamp,row['reminder_id']))
            con.execute('INSERT INTO membership_email_attempts VALUES (?,?)',(uuid4().hex,timestamp))
        state='sent'
        try:
            with closing(get_connection()) as con:
                current=con.execute('SELECT expires_at FROM memberships WHERE user_id=?',(row['user_id'],)).fetchone()
            if not current or current['expires_at']!=row['expires_at'] or current['expires_at']<=now():
                state='superseded'
            else:
                mail.send_membership_notice(row['email'],row['expires_at'],row['reminder_id'])
                sent+=1
        except mail.EmailDeliveryUncertain:
            state='uncertain'
            logger.warning('会员邮件发送结果待人工核对: %s',row['reminder_id'])
        except Exception:
            state='failed'
            logger.warning('会员邮件暂未发送: %s',row['reminder_id'])
        with closing(get_connection()) as con, con:
            con.execute('UPDATE membership_reminders SET state=?,sent_at=? WHERE reminder_id=?',(state,now() if state=='sent' else None,row['reminder_id']))
    return sent


def run(stop):
    while not stop.is_set():
        try:
            process_due()
        except Exception:
            logger.exception('会员提醒任务暂不可用')
        try:
            from app.api.assets import purge_expired_trash
            purge_expired_trash()
        except Exception:
            logger.exception('回收站清理任务暂不可用')
        stop.wait(60)
