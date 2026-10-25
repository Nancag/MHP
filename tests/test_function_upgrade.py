import unittest
from contextlib import closing
from unittest.mock import patch
from pydantic import ValidationError
from PIL import Image
import test_password_auth as password_tests
import test_workspace as workspace_tests
from app.services import auth_service as service
from app.models import db
from app.services.cost_estimator import CostInput,estimate
from app.services.template_catalog import catalog
from app.services.product_set_service import SetPage,ProductSetSpec,render_copy,render_material,build_instruction
from app.api.workspace import Template

class ResetTests(unittest.TestCase):
    setUp=password_tests.PasswordTests.setUp
    register=password_tests.PasswordTests.register
    def request_reset(self):
        with closing(db.get_connection()) as con,con:con.execute('UPDATE auth_codes SET created_at=created_at-61')
        sent=[]
        with patch.object(service,'send_reset_email',side_effect=lambda e,c,i:sent.append((c,i))):
            status,result=self.client.call('POST','/api/auth/password/reset-code',{'email':self.email})
        self.assertEqual(status,200,result)
        return sent,result
    def test_reset_sessions_single_use_and_login(self):
        self.register();sent,_=self.request_reset();code,cid=sent[0]
        value={'challenge_id':cid,'code':code,'new_password':'Replacement-password-900!'}
        self.assertEqual(self.client.call('POST','/api/auth/password/reset',value)[0],200)
        self.assertEqual(self.client.call('GET','/api/auth/me')[0],401)
        self.assertEqual(self.client.call('POST','/api/auth/password/reset',value)[0],400)
        self.assertEqual(self.client.call('POST','/api/auth/login',{'email':self.email,'password':self.password})[0],401)
        self.assertEqual(self.client.call('POST','/api/auth/login',{'email':self.email,'password':value['new_password']})[0],200)
    def test_reset_unknown_no_email_no_account(self):
        sent,result=self.request_reset();self.assertEqual(sent,[])
        self.assertIn('challenge_id',result)
        with closing(db.get_connection()) as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)
    def test_cross_origin_and_shared_cooldown(self):
        self.register()
        self.assertEqual(self.client.call('POST','/api/auth/password/reset-code',{'email':self.email},origin='https://untrusted.example')[0],403)
        self.assertEqual(self.client.call('POST','/api/auth/password/reset-code',{'email':self.email})[0],429)
        self.assertEqual(self.client.call('POST','/api/auth/password/reset',{'challenge_id':'0'*32,'code':'000000','new_password':self.password},origin='https://untrusted.example')[0],403)
    def test_reset_during_login_cannot_create_stale_password_session(self):
        from app.services import password_auth
        self.register();user_id=self.client.call('GET','/api/auth/me')[1]['user']['user_id']
        original=password_auth.matches
        def change(value,row):
            result=original(value,row)
            salt,hashed=password_auth.encode_password('Replacement-password-222!')
            with closing(db.get_connection()) as con,con:con.execute('UPDATE password_credentials SET salt=?,password_hash=? WHERE user_id=?',(salt,hashed,user_id))
            return result
        with patch.object(password_auth,'matches',side_effect=change):
            self.assertEqual(self.client.call('POST','/api/auth/login',{'email':self.email,'password':self.password})[0],401)
    def test_purpose_expiry_attempts_and_weak_password(self):
        self.client.call('POST','/api/auth/email/code',{'email':self.email});code,cid=self.codes[-1]
        request={'challenge_id':cid,'code':code,'new_password':self.password}
        self.assertEqual(self.client.call('POST','/api/auth/password/reset',request)[0],400)
        self.register_after_cooldown()
        sent,_=self.request_reset();code,cid=sent[0];request.update(challenge_id=cid,code=code,new_password='tiny')
        self.assertEqual(self.client.call('POST','/api/auth/password/reset',request)[0],422)
        request['new_password']=self.password
        # Reset codes cannot register a new credential through the registration path.
        self.assertEqual(self.client.call('POST','/api/auth/register',{'challenge_id':cid,'code':code,'username':'QA','password':self.password})[0],400)
        request['code']='000000' if code!='000000' else '111111'
        for _ in range(4):self.assertEqual(self.client.call('POST','/api/auth/password/reset',request)[0],400)
        request['code']=code
        self.assertEqual(self.client.call('POST','/api/auth/password/reset',request)[0],400)
        with closing(db.get_connection()) as con,con:con.execute('UPDATE auth_codes SET created_at=created_at-61')
        sent,_=self.request_reset();code,cid=sent[0]
        with closing(db.get_connection()) as con,con:con.execute('UPDATE auth_codes SET expires_at=0 WHERE challenge_id=?',(cid,))
        request.update(challenge_id=cid,code=code)
        self.assertEqual(self.client.call('POST','/api/auth/password/reset',request)[0],400)
    def register_after_cooldown(self):
        with closing(db.get_connection()) as con,con:con.execute('UPDATE auth_codes SET created_at=created_at-61')
        self.register()

class CostTests(unittest.TestCase):
    def data(self,**kwargs):
        return dict(purchase='100',package_weight_g='500',freight_per_g='0.02',customs_percent='10',commission_percent='10',loss_percent='5',customs_base='purchase',**kwargs)
    def test_reverse_equation_and_bases(self):
        data=self.data();out=estimate(CostInput(**data));self.assertEqual(out['cost'],'157.89');self.assertEqual(out['selling_price'],'315.78')
        data['customs_base']='purchase_freight';self.assertEqual(estimate(CostInput(**data))['customs'],'11.00')
        data.update(commission_percent='0',loss_percent='0',customs_percent='0');out=estimate(CostInput(**data));self.assertEqual(out['cost'],'110.00')
    def test_invalid_rates_nan_and_missing_basis(self):
        for key,value in [('commission_percent','50'),('loss_percent','100'),('purchase','NaN'),('freight_per_g','-1'),('package_weight_g','0')]:
            data=self.data();data[key]=value
            with self.assertRaises(ValidationError):CostInput(**data)
        data=self.data();del data['customs_base']
        with self.assertRaises(ValidationError):CostInput(**data)

class TemplateUpgradeTests(unittest.TestCase):
    setUp=workspace_tests.WorkspaceTests.setUp
    def test_catalog_import_export_ownership_and_secrets(self):
        for item in catalog()['items']:
            Template(name=item['name'],payload=item['payload'])
        source=catalog()['items'][0]
        value={'format':'mhp-template','version':1,'template':{k:source[k] for k in ('name','description','payload')}}
        status,item=self.client.call('POST','/api/workspace/templates/import',value);self.assertEqual(status,201,item)
        tid=item['template_id'];status,data=self.client.call('GET',f'/api/workspace/templates/{tid}/export');self.assertEqual(status,200);self.assertEqual(data['version'],1)
        self.user['user_id']='other';self.assertEqual(self.client.call('GET',f'/api/workspace/templates/{tid}/export')[0],404)
        value['template']['payload']['params']['api_key']='unsafe';self.assertEqual(self.client.call('POST','/api/workspace/templates/import',value)[0],422)
        value['version']=2;self.assertEqual(self.client.call('POST','/api/workspace/templates/import',value)[0],422)
        self.assertEqual(self.client.call('POST','/api/workspace/templates',{'name':'bad','payload':{'prompt':123}})[0],422)
    def test_plain_render_and_instruction(self):
        source=self.root/'original.png';Image.new('RGB',(90,120),'red').save(source)
        page=SetPage(asset_id='a'*32,kind='main',title='Товар',no_overlay=True)
        image=render_copy(source,page,(90,120));self.assertEqual(image.getpixel((0,0)),(255,0,0))
        local=render_material(source,page,(180,240));self.assertEqual(local.getpixel((0,0)),(255,255,255));self.assertEqual(local.getpixel((90,120)),(255,0,0))
        spec=ProductSetSpec(product_name='Товар',count=1,pages=[page]);instruction=build_instruction(spec,0);self.assertIn('pure white',instruction);self.assertNotIn('upper 27%',instruction)


class CostApiTests(unittest.TestCase):
    def test_authenticated_estimate_and_validation(self):
        from fastapi import FastAPI
        from app.api import mkhp,auth
        from support_client import Client
        app=FastAPI();app.include_router(mkhp.router)
        client=Client(app)
        self.assertEqual(client.call('POST','/api/mkhp/cost-estimate',{})[0],401)
        app.dependency_overrides[auth.require_user]=lambda:{'user_id':'isolated'}
        data={'purchase':'100','package_weight_g':'500','freight_per_g':'0.02','customs_percent':'10','commission_percent':'10','loss_percent':'5','customs_base':'purchase'}
        status,result=client.call('POST','/api/mkhp/cost-estimate',data)
        self.assertEqual(status,200,result);self.assertEqual(result['selling_price'],'315.78')
        data['commission_percent']='50';self.assertEqual(client.call('POST','/api/mkhp/cost-estimate',data)[0],422)
