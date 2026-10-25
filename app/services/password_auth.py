"""Password sign-in and device sessions. Local UI markers are never authentication."""
import hashlib
import hmac
import secrets
from contextlib import closing
from fastapi import HTTPException
from app.models.db import get_connection
from app.services import auth_service as auth

def encode_password(value):
    if not isinstance(value,str) or not 10<=len(value)<=128 or len(value.strip())<10:
        raise HTTPException(422,'密码需为10至128个字符')
    salt=secrets.token_hex(16)
    result=hashlib.pbkdf2_hmac('sha256',value.encode(),bytes.fromhex(salt),600000).hex()
    return salt,result

def matches(value,row):
    if not isinstance(value,str) or len(value)>128:return False
    salt=row['salt'] if row else '0'*32
    expected=row['password_hash'] if row else '0'*64
    result=hashlib.pbkdf2_hmac('sha256',value.encode(),bytes.fromhex(salt),600000).hex()
    return hmac.compare_digest(result,expected) and row is not None

def login(email,password,client,remember=True):
    email=auth.normalize_email(email);stamp=auth.now();key=auth.digest(client+'|'+email)
    with closing(get_connection()) as con,con:
        con.execute('BEGIN IMMEDIATE');con.execute('DELETE FROM password_attempts WHERE created_at<?',(stamp-900,))
        if con.execute('SELECT COUNT(*) FROM password_attempts WHERE attempt_key=?',(key,)).fetchone()[0]>=10:raise HTTPException(429,'尝试次数过多，请15分钟后重试')
        con.execute('INSERT INTO password_attempts VALUES (?,?)',(key,stamp))
        row=con.execute('SELECT u.user_id,u.email,u.username,p.salt,p.password_hash FROM users u JOIN password_credentials p ON p.user_id=u.user_id WHERE u.email=?',(email,)).fetchone()
    if not matches(password,row):raise HTTPException(401,'邮箱或密码不正确；旧账号请先在已登录设备的设置中设置密码')
    token=secrets.token_urlsafe(32);ttl=auth.REMEMBER_TTL if remember else auth.SESSION_TTL
    with closing(get_connection()) as con,con:
        con.execute('BEGIN IMMEDIATE')
        current=con.execute('SELECT password_hash FROM password_credentials WHERE user_id=?',(row['user_id'],)).fetchone()
        if not current or not hmac.compare_digest(current['password_hash'],row['password_hash']):
            raise HTTPException(401,'密码已变更，请重新登录')
        con.execute('DELETE FROM password_attempts WHERE attempt_key=?',(key,))
        con.execute('INSERT INTO auth_sessions VALUES (?,?,?,?,?)',(auth.digest(token),row['user_id'],stamp,stamp+ttl,int(remember)))
    return {k:row[k] for k in ('user_id','email','username')},token,ttl

def set_password(user_id,current_password,new_password):
    encoded=encode_password(new_password)
    with closing(get_connection()) as con,con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM password_credentials WHERE user_id=?',(user_id,)).fetchone()
        if row and not matches(current_password,row):raise HTTPException(400,'当前密码不正确')
        con.execute('INSERT OR REPLACE INTO password_credentials VALUES (?,?,?,?)',(user_id,*encoded,auth.now()))
    return {'saved':True}


def reset_password(challenge_id,code,new_password):
    if not 10<=len(new_password)<=128 or len(new_password.strip())<10:
        raise HTTPException(422,'密码需为10至128个字符')
    stamp=auth.now()
    with closing(get_connection()) as con,con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM auth_codes WHERE challenge_id=?',(challenge_id,)).fetchone()
        if not row or row['consumed'] or row['attempts']>=5 or row['expires_at']<=stamp:
            raise HTTPException(400,'验证码无效或已过期，请重新获取')
        if not hmac.compare_digest(row['code_hash'],auth.code_digest('reset:'+challenge_id,code)):
            con.execute('UPDATE auth_codes SET attempts=attempts+1 WHERE challenge_id=?',(challenge_id,));con.commit()
            raise HTTPException(400,'验证码错误或用途不符')
        user=con.execute('SELECT user_id FROM users WHERE email=?',(row['email'],)).fetchone()
        if not user:raise HTTPException(400,'验证码无效或已过期，请重新获取')
        salt,hashed=encode_password(new_password)
        con.execute('INSERT OR REPLACE INTO password_credentials VALUES (?,?,?,?)',(user['user_id'],salt,hashed,stamp))
        con.execute('UPDATE auth_codes SET consumed=1 WHERE email=?',(row['email'],))
        con.execute('DELETE FROM auth_sessions WHERE user_id=?',(user['user_id'],))
    return {'reset':True,'message':'密码已重置，请使用新密码重新登录'}
