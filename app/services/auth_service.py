"""Small SQLite authentication service. No password or third-party sign-in."""
import hashlib
import hmac
from contextlib import closing
import json
import os
import re
import secrets
import smtplib
from app.services.outbound_tls import SMTP_SSL
import ssl
import time
import unicodedata
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, build_opener, ProxyHandler

from fastapi import HTTPException

from app import config  # Loads local configuration without exposing credentials.
from app.models.db import get_connection

CODE_TTL = 600
SESSION_TTL = 12 * 3600
REMEMBER_TTL = 365 * 24 * 3600
COOKIE_NAME = "mhp_session"
ALLOWED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}


def now():
    return int(time.time())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _secret():
    configured = os.environ.get("AUTH_SECRET")
    if configured:
        return configured.encode()
    path = config.PROJECT_ROOT / "data" / ".auth-secret"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    return path.read_bytes()


def code_digest(challenge_id, code):
    return hmac.new(_secret(), f"{challenge_id}:{code}".encode(), hashlib.sha256).hexdigest()


def normalize_email(value):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
        raise HTTPException(422, "请输入有效邮箱")
    return value


def normalize_username(value):
    value = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(value) <= 20 or any(unicodedata.category(c).startswith("C") for c in value):
        raise HTTPException(422, "用户名必填，最多 20 个字符，不能包含控制字符")
    return value


SMTP_HOSTS = {"163.com": "smtp.163.com", "126.com": "smtp.126.com", "yeah.net": "smtp.yeah.net"}


def email_provider():
    return os.environ.get("AUTH_EMAIL_PROVIDER", "netease_smtp").strip().lower()


def _smtp_account():
    username = os.environ.get("SMTP_USERNAME", "").strip().lower()
    domain = username.rpartition("@")[2]
    if domain not in SMTP_HOSTS or not re.fullmatch(r"[a-z0-9_.+-]+@(?:163\.com|126\.com|yeah\.net)", username):
        return None
    return username, SMTP_HOSTS[domain]


def email_ready():
    if email_provider() == "netease_smtp":
        return bool(_smtp_account() and os.environ.get("SMTP_AUTH_CODE", "").strip())
    if email_provider() == "resend":
        return bool(os.environ.get("RESEND_API_KEY") and os.environ.get("AUTH_EMAIL_FROM"))
    return False


def send_email(email, code, challenge_id):
    if not email_ready():
        raise HTTPException(503, "邮箱服务尚未配置，请联系管理员")
    email = normalize_email(email)
    if email_provider() == "netease_smtp":
        return _send_smtp(email, code)
    return _send_resend(email, code, challenge_id)


def _send_smtp(email, code):
    return _deliver_smtp(email,'MHP 登录验证码',f"你的 MHP 验证码是 {code}，10 分钟内有效。请勿向他人透露。如非本人操作，请忽略。")


class EmailDeliveryUncertain(Exception):
    pass


def _deliver_smtp(email, subject, text, reference=None):
    username, host = _smtp_account()
    message = EmailMessage()
    message["From"] = formataddr(("MHP", username))
    message["To"] = email
    message["Subject"] = subject
    message["Message-ID"] = f'<mhp-membership-{reference}@{username.rpartition("@")[2]}>' if reference else make_msgid(domain=username.rpartition("@")[2])
    message.set_content(text)
    started=False
    accepted=False
    try:
        # Verified TLS only. Fixed provider hosts; no debug logging or automatic retries.
        with SMTP_SSL(host, 465, timeout=15, context=ssl.create_default_context()) as client:
            client.login(username, os.environ["SMTP_AUTH_CODE"].strip())
            started=True
            rejected = client.send_message(message, from_addr=username, to_addrs=[email])
            if rejected:
                raise HTTPException(503, "网易 SMTP 未接受收件地址，请检查邮箱地址")
            accepted=True
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(503, "网易 SMTP 认证失败，请检查客户端协议是否开启及授权码是否有效") from None
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
        # An explicit negative reply confirms that SMTP did not accept the message.
        raise HTTPException(503, "网易 SMTP 未接受邮件，请检查地址或账号限制后重试") from None
    except (smtplib.SMTPException, OSError):
        if accepted:
            # DATA already succeeded. A failed QUIT must not invalidate a delivered code.
            return
        if reference and started:
            raise EmailDeliveryUncertain('SMTP acknowledgement uncertain') from None
        raise HTTPException(503, "网易 SMTP 发送失败，请检查网络、账号限制或稍后重试") from None


def _send_resend(email, code, challenge_id, subject=None, text=None):
    # Fixed provider endpoint; do not permit user-supplied URLs or send images.
    payload = json.dumps({
        "from": os.environ["AUTH_EMAIL_FROM"], "to": [email],
        "subject": subject or "MHP 登录验证码",
        "text": text or f"你的 MHP 验证码是 {code}，10 分钟内有效。请勿向他人透露。如非本人操作，请忽略。",
    }).encode()
    request = Request("https://api.resend.com/emails", data=payload, method="POST", headers={
        "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
        "Content-Type": "application/json", "User-Agent": "MHP/Stage8",
        "Idempotency-Key": f"mhp-login-{challenge_id}",
    })
    try:
        from app.services.outbound_tls import HTTPSHandler,NoRedirect
        opener=build_opener(ProxyHandler({}),HTTPSHandler(),NoRedirect)
        with opener.open(request, timeout=15) as response:
            if not json.load(response).get("id"):
                raise HTTPException(503, "验证码发送失败，请稍后重试")
    except (HTTPError, URLError, TimeoutError, ValueError):
        # Provider errors may contain personal data; never log their bodies.
        raise HTTPException(503, "验证码发送失败，请检查邮箱服务配置或稍后重试") from None


def send_membership_notice(email,expires_at,reference):
    from datetime import datetime
    from app.services.credit_service import CHINA
    if not email_ready():
        raise HTTPException(503,'邮箱服务未配置')
    email=normalize_email(email)
    expires=datetime.fromtimestamp(expires_at,CHINA).strftime('%Y-%m-%d %H:%M 北京时间')
    text=f'你的 MHP 会员将于 {expires} 到期，剩余会员生成额度届时到期。注册及签到额度不受影响。可进入账户管理续费；如已续费，请以账户页面的最新有效期为准。本邮件不含支付链接，也不会自动扣款。'
    if email_provider()=='netease_smtp':
        return _deliver_smtp(email,'MHP 会员即将到期提醒',text,reference)
    return _send_resend(email,'',reference,'MHP 会员即将到期提醒',text)


def send_reset_email(email,code,challenge_id):
    subject='MHP 找回密码验证码'
    text=f'你的 MHP 找回密码验证码是 {code}，10分钟内有效。修改密码后所有设备需重新登录。如非本人操作，请忽略，不要透露验证码。'
    if email_provider()=='netease_smtp':return _deliver_smtp(email,subject,text,challenge_id)
    return _send_resend(email,code,challenge_id,subject,text)


def request_code(email, client, purpose='register'):
    if purpose not in ('register','reset'):raise ValueError('Unsupported code purpose')
    email = normalize_email(email)
    with closing(get_connection()) as lookup:
        exists=bool(lookup.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone())
        if purpose=='register' and lookup.execute('SELECT 1 FROM users u JOIN password_credentials p ON p.user_id=u.user_id WHERE u.email=?',(email,)).fetchone():
            raise HTTPException(409,'此账号已注册，请使用密码登录；已有登录设备可在设置中修改密码')
    if not email_ready():
        raise HTTPException(503, "邮箱服务尚未配置，请联系管理员")
    timestamp = now()
    challenge_id = secrets.token_hex(16)
    code = f"{secrets.randbelow(1000000):06d}"
    client_hash = hmac.new(_secret(), client.encode(), hashlib.sha256).hexdigest()
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM auth_codes WHERE created_at < ?", (timestamp - 86400,))
        connection.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (timestamp,))
        latest = connection.execute("SELECT MAX(created_at) FROM auth_codes WHERE email = ?", (email,)).fetchone()[0]
        email_count = connection.execute("SELECT COUNT(*) FROM auth_codes WHERE email = ? AND created_at > ?", (email, timestamp - 3600)).fetchone()[0]
        client_count = connection.execute("SELECT COUNT(*) FROM auth_codes WHERE client_hash = ? AND created_at > ?", (client_hash, timestamp - 3600)).fetchone()[0]
        daily_count = connection.execute("SELECT COUNT(*) FROM auth_codes WHERE created_at >= ?", (timestamp - timestamp % 86400,)).fetchone()[0]
        daily_count += connection.execute('SELECT COUNT(*) FROM membership_email_attempts WHERE created_at>=?',(timestamp-timestamp%86400,)).fetchone()[0]
        daily_limit = 10 if email_provider() == "netease_smtp" else 90
        if (latest is not None and timestamp - latest < 60) or email_count >= 5 or client_count >= 20 or daily_count >= daily_limit:
            raise HTTPException(429, "发送过于频繁，请稍后重试")
        connection.execute("INSERT INTO auth_codes VALUES (?, ?, ?, ?, ?, 0, 0, ?)",
                           (challenge_id, email, code_digest(('reset:' if purpose=='reset' else '')+challenge_id, code), timestamp, timestamp + CODE_TTL, client_hash))
        connection.commit()
    finally:
        connection.close()
    try:
        if purpose=='reset':
            if exists:send_reset_email(email,code,challenge_id)
        else:send_email(email, code, challenge_id)
    except Exception:
        with get_connection() as connection:
            connection.execute("UPDATE auth_codes SET consumed = 1 WHERE challenge_id = ?", (challenge_id,))
        connection.close()
        raise
    # Only successful delivery supersedes previous challenges.
    with get_connection() as connection:
        # Slow older deliveries must never invalidate a more recent challenge.
        connection.execute("""UPDATE auth_codes SET consumed = 1 WHERE email = ?
            AND rowid < (SELECT rowid FROM auth_codes WHERE challenge_id = ?)""", (email, challenge_id))
    connection.close()
    return {"challenge_id": challenge_id, "expires_in": CODE_TTL, "retry_after": 60}


def verify_code(challenge_id, code, username, remember, password=None):
    from app.services.password_auth import encode_password
    encoded=encode_password(password) if password is not None else None
    timestamp = now()
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM auth_codes WHERE challenge_id = ?", (challenge_id,)).fetchone()
        if not row or row["consumed"] or row["attempts"] >= 5 or row["expires_at"] <= timestamp:
            raise HTTPException(400, "验证码无效或已过期，请重新获取")
        if not hmac.compare_digest(row["code_hash"], code_digest(challenge_id, code)):
            connection.execute("UPDATE auth_codes SET attempts = attempts + 1 WHERE challenge_id = ?", (challenge_id,))
            connection.commit()
            raise HTTPException(400, "验证码错误")
        user = connection.execute("SELECT user_id, username FROM users WHERE email = ?", (row["email"],)).fetchone()
        if user and connection.execute('SELECT 1 FROM password_credentials WHERE user_id=?',(user['user_id'],)).fetchone():
            raise HTTPException(409,'账号已注册，请使用密码登录')
        if not user:
            if username is None:
                raise HTTPException(409, "首次注册请填写用户名")
            username = normalize_username(username or "")
            user = {"user_id": secrets.token_hex(16), "username": username}
            connection.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user["user_id"], row["email"], username, timestamp))
            from app.services.credit_service import ensure_wallet
            ensure_wallet(connection, user['user_id'])
        if encoded:
            connection.execute('INSERT INTO password_credentials VALUES (?,?,?,?)',(user['user_id'],*encoded,timestamp))
        token = secrets.token_urlsafe(32)
        ttl = REMEMBER_TTL if remember else SESSION_TTL
        connection.execute("UPDATE auth_codes SET consumed = 1 WHERE challenge_id = ?", (challenge_id,))
        connection.execute("INSERT INTO auth_sessions VALUES (?, ?, ?, ?, ?)",
                           (digest(token), user["user_id"], timestamp, timestamp + ttl, int(remember)))
        connection.commit()
        return {"user_id": user["user_id"], "username": user["username"], "email": row["email"]}, token, ttl
    finally:
        connection.close()


def session_user(token):
    if not token:
        return None
    connection = get_connection()
    try:
        row = connection.execute("""SELECT u.user_id, u.username, u.email FROM auth_sessions s
            JOIN users u ON s.user_id = u.user_id WHERE s.token_hash = ? AND s.expires_at > ?""",
                                 (digest(token), now())).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def revoke_session(token):
    connection = get_connection()
    try:
        connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (digest(token or ""),))
        connection.commit()
    finally:
        connection.close()
