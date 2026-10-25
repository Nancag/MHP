"""RSA2 page-payment integration. Disabled until explicitly configured."""
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from datetime import datetime
from app.services.credit_service import CHINA
from app.services.membership_service import PLANS


def configuration():
    if os.environ.get('ALIPAY_ENABLED','0')!='1':
        raise ValueError('Alipay is disabled')
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    app_id=os.environ.get('ALIPAY_APP_ID','').strip()
    seller_id=os.environ.get('ALIPAY_SELLER_ID','').strip()
    if not app_id.isdigit() or not seller_id.isdigit():
        raise ValueError('Missing merchant identifiers')
    urls={key:os.environ.get(key,'').strip() for key in ('ALIPAY_NOTIFY_URL','ALIPAY_RETURN_URL')}
    for value in urls.values():
        parsed=urlsplit(value)
        if parsed.scheme!='https' or not parsed.hostname or parsed.hostname in ('localhost','127.0.0.1','::1') or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('Public HTTPS callback URLs are required')
    environment=os.environ.get('ALIPAY_ENV','production')
    if environment not in ('production','sandbox'):
        raise ValueError('Invalid Alipay environment')
    if environment=='sandbox':
        from app.models import db
        from app.config import PROJECT_ROOT
        if db.DB_PATH.resolve()==(PROJECT_ROOT/'data'/'mhp.db').resolve():
            raise ValueError('Sandbox payments must use an isolated database')
    private=serialization.load_pem_private_key(Path(os.environ['ALIPAY_PRIVATE_KEY_PATH']).read_bytes(),password=None)
    public=serialization.load_pem_public_key(Path(os.environ['ALIPAY_PUBLIC_KEY_PATH']).read_bytes())
    if not isinstance(private,rsa.RSAPrivateKey) or not isinstance(public,rsa.RSAPublicKey) or min(private.key_size,public.key_size)<2048:
        raise ValueError('RSA keys must be at least 2048 bits')
    return {'app_id':app_id,'seller_id':seller_id,'private':private,'public':public,
            'notify_url':urls['ALIPAY_NOTIFY_URL'],'return_url':urls['ALIPAY_RETURN_URL'],
            'environment':environment,'gateway':'https://openapi.alipay.com/gateway.do' if environment=='production' else 'https://openapi-sandbox.dl.alipaydev.com/gateway.do'}


def ready():
    try:
        configuration()
        return True
    except (ValueError,TypeError,OSError,KeyError,ImportError):
        return False


def canonical(params,notification=False):
    excluded={'sign','sign_type'} if notification else {'sign'}
    return '&'.join(f'{key}={value}' for key,value in sorted(params.items()) if key not in excluded and value not in ('',None)).encode('utf-8')


def checkout_url(order,config=None):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    config=config or configuration()
    return_parts=urlsplit(config['return_url'])
    query=dict(parse_qsl(return_parts.query)); query['membership_order']=order['order_id']
    return_url=urlunsplit(return_parts._replace(query=urlencode(query)))
    params={
        'app_id':config['app_id'],'method':'alipay.trade.page.pay','format':'JSON','charset':'utf-8',
        'sign_type':'RSA2','timestamp':datetime.now(CHINA).strftime('%Y-%m-%d %H:%M:%S'),'version':'1.0',
        'notify_url':config['notify_url'],'return_url':return_url,
        'biz_content':json.dumps({'out_trade_no':order['order_id'],'product_code':'FAST_INSTANT_TRADE_PAY',
            'total_amount':f"{order['price_fen']//100}.{order['price_fen']%100:02d}",
            'subject':'MHP '+PLANS[order['plan_id']]['name'],'timeout_express':'30m'},ensure_ascii=False,separators=(',',':')),
    }
    params['sign']=base64.b64encode(config['private'].sign(canonical(params),padding.PKCS1v15(),hashes.SHA256())).decode('ascii')
    return config['gateway']+'?'+urlencode(params)


def verify_notification(params):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.exceptions import InvalidSignature
    config=configuration()
    if params.get('sign_type')!='RSA2' or params.get('app_id')!=config['app_id'] or params.get('seller_id')!=config['seller_id']:
        return False
    try:
        signature=base64.b64decode(params.get('sign',''),validate=True)
        config['public'].verify(signature,canonical(params,notification=True),padding.PKCS1v15(),hashes.SHA256())
        return True
    except (InvalidSignature,ValueError,TypeError):
        return False
