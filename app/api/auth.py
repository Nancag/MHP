import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, StrictBool

from app.services import auth_service as auth
from app.services import password_auth

router = APIRouter(prefix="/api/auth", tags=["用户认证"])


def check_origin(request: Request):
    origin = request.headers.get("origin")
    allowed = auth.ALLOWED_ORIGINS | {item.strip() for item in os.environ.get("AUTH_ALLOWED_ORIGINS", "").split(",") if item.strip()}
    if origin and origin not in allowed:
        raise HTTPException(403, "请求来源不受信任")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "不允许跨站请求")


def require_user(request: Request):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
    user = auth.session_user(request.cookies.get(auth.COOKIE_NAME))
    if not user:
        raise HTTPException(401, "请先登录")
    return user


CurrentUser = Annotated[dict, Depends(require_user)]


class SendCode(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class VerifyCode(BaseModel):
    challenge_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    code: str = Field(pattern=r"^[0-9]{6}$")
    username: str | None = Field(default=None, max_length=20)
    remember: StrictBool = False

class Register(VerifyCode):
    password:str=Field(min_length=10,max_length=128)
    remember:StrictBool=True

class Login(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=1,max_length=128)
    remember:StrictBool=True

class ChangePassword(BaseModel):
    current_password:str=Field(default='',max_length=128)
    new_password:str=Field(min_length=10,max_length=128)


class ResetPassword(BaseModel):
    challenge_id:str=Field(pattern=r'^[0-9a-f]{32}$')
    code:str=Field(pattern=r'^[0-9]{6}$')
    new_password:str=Field(min_length=10,max_length=128)


@router.post('/password/reset-code',dependencies=[Depends(check_origin)])
def reset_code(payload:SendCode,request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    result=auth.request_code(payload.email,request.client.host if request.client else 'local',purpose='reset')
    return {**result,'message':'若该邮箱已注册，将收到找回密码验证码'}


@router.post('/password/reset',dependencies=[Depends(check_origin)])
def reset_password_route(payload:ResetPassword,response:Response):
    response.headers['Cache-Control']='no-store'
    result=password_auth.reset_password(payload.challenge_id,payload.code,payload.new_password)
    response.delete_cookie(auth.COOKIE_NAME,path='/')
    return result

def cookie(response,token,ttl,remember):
    response.set_cookie(auth.COOKIE_NAME,token,max_age=ttl if remember else None,httponly=True,
        secure=os.environ.get('AUTH_COOKIE_SECURE','0')=='1',samesite='lax',path='/')
    response.headers['Cache-Control']='no-store'

@router.post('/register',dependencies=[Depends(check_origin)])
def register(payload:Register,request:Request,response:Response):
    user,token,ttl=auth.verify_code(payload.challenge_id,payload.code,payload.username,payload.remember,payload.password)
    auth.revoke_session(request.cookies.get(auth.COOKIE_NAME));cookie(response,token,ttl,payload.remember)
    return {'user':{**user,'password_configured':True}}

@router.post('/login',dependencies=[Depends(check_origin)])
def password_login(payload:Login,request:Request,response:Response):
    user,token,ttl=password_auth.login(payload.email,payload.password,request.client.host if request.client else 'local',payload.remember)
    auth.revoke_session(request.cookies.get(auth.COOKIE_NAME));cookie(response,token,ttl,payload.remember)
    return {'user':{**user,'password_configured':True}}

@router.post('/password')
def change_password(payload:ChangePassword,user:CurrentUser,request:Request):
    result=password_auth.set_password(user['user_id'],payload.current_password,payload.new_password)
    from contextlib import closing
    from app.models.db import get_connection
    with closing(get_connection()) as con,con:
        con.execute('DELETE FROM auth_sessions WHERE user_id=? AND token_hash!=?',(user['user_id'],auth.digest(request.cookies.get(auth.COOKIE_NAME,''))))
    return result


@router.get("/config")
def get_config(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"email_enabled": auth.email_ready(), "sms_enabled": False}


@router.post("/email/code", dependencies=[Depends(check_origin)])
def send_code(payload: SendCode, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return auth.request_code(payload.email, request.client.host if request.client else "local")


@router.post("/email/verify", dependencies=[Depends(check_origin)])
def verify(payload: VerifyCode, request: Request, response: Response):
    if os.environ.get('AUTH_LEGACY_CODE_LOGIN','0')!='1':
        raise HTTPException(410,'验证码仅用于注册或首次绑定密码，请使用注册或密码登录')
    user, token, ttl = auth.verify_code(payload.challenge_id, payload.code, payload.username, payload.remember)
    # Rotate the current browser session after successful reauthentication.
    auth.revoke_session(request.cookies.get(auth.COOKIE_NAME))
    response.set_cookie(auth.COOKIE_NAME, token, max_age=ttl if payload.remember else None,
                        httponly=True, secure=os.environ.get("AUTH_COOKIE_SECURE", "0") == "1",
                        samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"user": {**user,'password_configured':False}}


@router.get("/me")
def me(user: CurrentUser, response: Response, request:Request):
    response.headers["Cache-Control"] = "no-store"
    from contextlib import closing
    from app.models.db import get_connection
    with closing(get_connection()) as con,con:
        user={**user,'password_configured':bool(con.execute('SELECT 1 FROM password_credentials WHERE user_id=?',(user['user_id'],)).fetchone())}
        row=con.execute('SELECT remember FROM auth_sessions WHERE token_hash=?',(auth.digest(request.cookies.get(auth.COOKIE_NAME,'')),)).fetchone()
        if row and row['remember']:
            con.execute('UPDATE auth_sessions SET expires_at=? WHERE token_hash=?',(auth.now()+auth.REMEMBER_TTL,auth.digest(request.cookies.get(auth.COOKIE_NAME,''))))
            cookie(response,request.cookies[auth.COOKIE_NAME],auth.REMEMBER_TTL,True)
    return {"user": user}


@router.post("/logout", dependencies=[Depends(check_origin)])
def logout(request: Request, response: Response):
    auth.revoke_session(request.cookies.get(auth.COOKIE_NAME))
    response.delete_cookie(auth.COOKIE_NAME, path="/", samesite="lax", httponly=True,
                           secure=os.environ.get("AUTH_COOKIE_SECURE", "0") == "1")
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}
