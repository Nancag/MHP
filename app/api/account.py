import logging
from urllib.parse import parse_qsl
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ConfigDict
from app.api.auth import CurrentUser
from app.services import credit_service, membership_service, alipay_service

logger=logging.getLogger(__name__)
router=APIRouter(prefix='/api/account',tags=['额度与会员'])


@router.get('')
def account(user:CurrentUser,response:Response):
    response.headers['Cache-Control']='no-store'
    payment_enabled=alipay_service.ready()
    return {**credit_service.summary(user['user_id']),
            'price_per_credit_fen':membership_service.PRICE_PER_CREDIT_FEN,
            'minimum_recharge':membership_service.MIN_CREDITS,'maximum_recharge':membership_service.MAX_CREDITS,
            'payment_enabled':payment_enabled,'payment_provider':'alipay' if payment_enabled else None,
            'orders':membership_service.list_orders(user['user_id'])}


@router.post('/checkin')
def checkin(user:CurrentUser,response:Response):
    response.headers['Cache-Control']='no-store'
    return credit_service.checkin(user['user_id'])


class OrderRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    credits:int=Field(ge=membership_service.MIN_CREDITS,le=membership_service.MAX_CREDITS)
    request_id:str=Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')


@router.post('/orders',status_code=201)
def order(payload:OrderRequest,user:CurrentUser,response:Response):
    response.headers['Cache-Control']='no-store'
    try:
        config=alipay_service.configuration()
    except (ValueError,TypeError,OSError,KeyError,ImportError):
        raise HTTPException(503,'额度充值暂未开放，请稍后再试') from None
    record=membership_service.create_order(user['user_id'],payload.credits,payload.request_id,config['app_id'],config['seller_id'])
    public=membership_service.public_order(record)
    if record['status']=='pending' and record['payment_deadline']>credit_service.now():
        public['checkout_url']=alipay_service.checkout_url(record,config)
    return public


class RedeemRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    code:str=Field(min_length=8,max_length=64)


@router.post('/redeem')
def redeem(payload:RedeemRequest,user:CurrentUser,response:Response):
    response.headers['Cache-Control']='no-store'
    return membership_service.redeem(user['user_id'],payload.code)


@router.get('/orders/{order_id}')
def order_status(order_id:str,user:CurrentUser,response:Response):
    response.headers['Cache-Control']='no-store'
    return membership_service.get_order(user['user_id'],order_id)


@router.post('/alipay/notify')
async def notify(request:Request):
    # This server-to-server callback is authenticated by RSA2, never by a browser return.
    if request.headers.get('content-type','').split(';')[0]!='application/x-www-form-urlencoded':
        return PlainTextResponse('failure',status_code=400)
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>16384:
            return PlainTextResponse('failure',status_code=413)
    try:
        pairs=parse_qsl(body.decode('utf-8'),keep_blank_values=True,max_num_fields=100)
        payload=dict(pairs)
        if len(payload)!=len(pairs) or not alipay_service.verify_notification(payload):
            return PlainTextResponse('failure',status_code=400)
        membership_service.apply_verified_payment(payload)
    except HTTPException as exc:
        return PlainTextResponse('failure',status_code=exc.status_code)
    except (ValueError,UnicodeError,TypeError,OSError,KeyError):
        return PlainTextResponse('failure',status_code=503)
    except Exception:
        logger.exception('支付宝通知处理失败；未确认到账')
        return PlainTextResponse('failure',status_code=503)
    return PlainTextResponse('success')
