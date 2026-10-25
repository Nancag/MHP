import os,tempfile,unittest
from pathlib import Path
from contextlib import ExitStack,closing
from unittest.mock import patch
from fastapi import FastAPI
from app.models import db
from app.api import auth
from app.services import auth_service as service,password_auth
from support_client import Client

class PasswordTests(unittest.TestCase):
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        folder=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(db,'DB_PATH',folder/'test.db'))
        stack.enter_context(patch.dict(os.environ,{'AUTH_SECRET':'isolated-test','AUTH_COOKIE_SECURE':'0','AUTH_LEGACY_CODE_LOGIN':'0'}))
        stack.enter_context(patch.object(service,'email_ready',return_value=True))
        self.codes=[];stack.enter_context(patch.object(service,'send_email',side_effect=lambda e,c,i:self.codes.append((c,i))))
        db.init_db();app=FastAPI();app.include_router(auth.router);self.client=Client(app)
        self.email='password@example.com';self.password='Long-password-100!'
    def register(self):
        self.assertEqual(self.client.call('POST','/api/auth/email/code',{'email':self.email})[0],200)
        code,challenge=self.codes[-1]
        status,value=self.client.call('POST','/api/auth/register',{'challenge_id':challenge,'code':code,'username':'QA','password':self.password,'remember':True})
        self.assertEqual(status,200,value);return value['user']
    def test_register_once_then_password_login_without_mail(self):
        user=self.register();self.assertTrue(user['password_configured'])
        with closing(db.get_connection()) as con:
            row=con.execute('SELECT * FROM password_credentials').fetchone();self.assertNotEqual(row['password_hash'],self.password)
        self.client.call('POST','/api/auth/logout',{})
        self.assertEqual(self.client.call('POST','/api/auth/email/code',{'email':self.email})[0],409)
        self.assertEqual(self.client.call('POST','/api/auth/login',{'email':self.email,'password':self.password})[0],200)
        self.assertEqual(len(self.codes),1)
    def test_persistent_device_cookie_and_server_validation(self):
        self.register();cookie=next(v.decode() for k,v in self.client.headers if k==b'set-cookie')
        self.assertIn('Max-Age=31536000',cookie);self.assertIn('HttpOnly',cookie)
        self.assertEqual(self.client.call('GET','/api/auth/me')[0],200)
        self.client.cookie='mhp_session=fake-local-registration-record';self.assertEqual(self.client.call('GET','/api/auth/me')[0],401)
    def test_legacy_account_can_bind_password_from_logged_device(self):
        with closing(db.get_connection()) as con,con:con.execute("INSERT INTO users VALUES ('legacy','legacy@example.com','Old',0)")
        password_auth.set_password('legacy','',self.password)
        self.assertEqual(password_auth.login('legacy@example.com',self.password,'local')[0]['user_id'],'legacy')
    def test_wrong_password_and_rate_limit(self):
        self.register()
        for _ in range(10):self.assertEqual(self.client.call('POST','/api/auth/login',{'email':self.email,'password':'wrong-password'})[0],401)
        self.assertEqual(self.client.call('POST','/api/auth/login',{'email':self.email,'password':self.password})[0],429)
    def test_password_change_requires_current_and_revokes_other_sessions(self):
        self.register();other=Client(self.client.app)
        self.assertEqual(other.call('POST','/api/auth/login',{'email':self.email,'password':self.password})[0],200)
        self.assertEqual(self.client.call('POST','/api/auth/password',{'current_password':'wrong','new_password':'Another-password-100!'})[0],400)
        self.assertEqual(self.client.call('POST','/api/auth/password',{'current_password':self.password,'new_password':'Another-password-100!'})[0],200)
        self.assertEqual(self.client.call('GET','/api/auth/me')[0],200);self.assertEqual(other.call('GET','/api/auth/me')[0],401)
    def test_weak_registration_password_does_not_consume_code(self):
        self.client.call('POST','/api/auth/email/code',{'email':self.email});code,challenge=self.codes[-1]
        self.assertEqual(self.client.call('POST','/api/auth/register',{'challenge_id':challenge,'code':code,'username':'QA','password':'tiny'})[0],422)
        self.assertEqual(self.client.call('POST','/api/auth/register',{'challenge_id':challenge,'code':code,'username':'QA','password':self.password})[0],200)

    def test_deprecated_code_login_is_disabled(self):
        self.assertEqual(self.client.call('POST','/api/auth/email/verify',{'challenge_id':'0'*32,'code':'000000'})[0],410)

    def test_invalid_challenge_never_derives_password_and_requests_are_rate_limited(self):
        payload={'challenge_id':'0'*32,'code':'000000','username':'QA','password':self.password,'remember':True}
        with patch.object(password_auth,'encode_password') as derive:
            for _ in range(60):
                self.assertEqual(self.client.call('POST','/api/auth/register',payload)[0],400)
            self.assertEqual(self.client.call('POST','/api/auth/register',payload)[0],429)
        derive.assert_not_called()
