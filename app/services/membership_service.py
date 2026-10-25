from calendar import monthrange
from contextlib import closing
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from fastapi import HTTPException
from app.models.db import get_connection
from app.services.credit_service import CHINA, now, ensure_wallet, grant

PLANS = {
    'day': {'name':'1 天会员','name_en':'1 day','price_fen':490,'credits':10,'days':1,'months':0},
    'month': {'name':'1 个月会员','name_en':'1 month','price_fen':4900,'credits':120,'days':0,'months':1},
    'quarter': {'name':'3 个月会员','name_en':'3 months','price_fen':13900,'credits':360,'days':0,'months':3},
}


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


def create_order(user_id,plan_id,request_key,app_id,seller_id):
    if plan_id not in PLANS:
        raise HTTPException(400,'会员档位无效')
    plan=PLANS[plan_id]
    with closing(get_connection()) as con, con:
        con.execute('BEGIN IMMEDIATE')
        existing=con.execute('SELECT * FROM membership_orders WHERE user_id=? AND request_key=?',(user_id,request_key)).fetchone()
        if existing:
            if existing['plan_id']!=plan_id:
                raise HTTPException(409,'同一订单请求不能更换会员档位')
            return dict(existing)
        # Repeated clicks/new browser tabs reuse an unpaid order for the same plan.
        existing=con.execute("SELECT * FROM membership_orders WHERE user_id=? AND plan_id=? AND status='pending' AND payment_deadline>? ORDER BY created_at DESC LIMIT 1",(user_id,plan_id,now())).fetchone()
        if existing:
            return dict(existing)
        timestamp=now()
        order_id=uuid4().hex
        con.execute('''INSERT INTO membership_orders
            (order_id,user_id,request_key,plan_id,price_fen,credits,days,months,status,app_id,seller_id,created_at,payment_deadline)
            VALUES (?,?,?,?,?,?,?,?,'pending',?,?,?,?)''',
            (order_id,user_id,request_key,plan_id,plan['price_fen'],plan['credits'],plan['days'],plan['months'],app_id,seller_id,timestamp,timestamp+1800))
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
        if not row or amount!=row['price_fen'] or payload.get('app_id')!=row['app_id'] or payload.get('seller_id')!=row['seller_id']:
            raise HTTPException(400,'支付通知与订单不匹配')
        status=payload.get('trade_status')
        if status not in ('TRADE_SUCCESS','TRADE_FINISHED'):
            if status=='TRADE_CLOSED':
                if row['status']=='paid':
                    if trade_no!=row['trade_no']:
                        raise HTTPException(400,'交易编号不匹配')
                    _revoke_refunded_order(con,row)
                elif row['status']=='pending':
                    con.execute("UPDATE membership_orders SET status='closed' WHERE order_id=?",(order_id,))
            return
        if not trade_no or len(trade_no)>128:
            raise HTTPException(400,'交易编号无效')
        if row['status']=='paid':
            if row['trade_no']!=trade_no:
                raise HTTPException(400,'交易编号不匹配')
            return
        if row['status']=='refunded':
            return  # Ignore an older success notification arriving after a verified full refund.
        if row['status']=='closed':
            raise HTTPException(409,'订单已关闭，请人工核对')
        if con.execute('SELECT 1 FROM membership_orders WHERE trade_no=?',(trade_no,)).fetchone():
            raise HTTPException(400,'交易编号重复')
        timestamp=now()
        member=con.execute('SELECT expires_at FROM memberships WHERE user_id=?',(row['user_id'],)).fetchone()
        base=max(timestamp,member['expires_at'] if member else 0)
        expiry=add_duration(base,row['days'],row['months'])
        ensure_wallet(con,row['user_id'])
        # Renewal extends unexpired paid credits; expired credits are never resurrected.
        con.execute("UPDATE credit_grants SET expires_at=? WHERE user_id=? AND source='membership' AND expires_at>?",(expiry,row['user_id'],timestamp))
        grant(con,row['user_id'],'membership',order_id,row['credits'],expiry)
        con.execute('''INSERT INTO memberships VALUES (?,?,?,?) ON CONFLICT(user_id)
            DO UPDATE SET plan_id=excluded.plan_id,expires_at=excluded.expires_at,updated_at=excluded.updated_at''',(row['user_id'],row['plan_id'],expiry,timestamp))
        con.execute("UPDATE membership_orders SET status='paid',paid_at=?,trade_no=?,membership_expires_at=? WHERE order_id=?",(timestamp,trade_no,expiry,order_id))
        con.execute("UPDATE membership_reminders SET state='superseded' WHERE user_id=? AND state IN ('pending','failed')",(row['user_id'],))
        lead=6*3600 if row['days'] else 3*86400
        con.execute('INSERT OR IGNORE INTO membership_reminders (reminder_id,user_id,expires_at,due_at) VALUES (?,?,?,?)',(uuid4().hex,row['user_id'],expiry,expiry-lead))


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
