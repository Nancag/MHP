"""Isolated synthetic regression cases. No live accounts, money or network."""
import base64
from contextlib import ExitStack, closing
import io
import json
import os
from pathlib import Path
import smtplib
import tempfile
import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from PIL import Image
from app.models import db
from app.services import auth_service as mail, reference_service as image, credit_service
from app.services import membership_service as membership, alipay_service


class MailBoundaries(unittest.TestCase):
    def setUp(self):
        stack=ExitStack(); self.addCleanup(stack.close)
        self.folder=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(db,'DB_PATH',self.folder/'synthetic.db'))
        stack.enter_context(patch.dict(os.environ,{'SMTP_USERNAME':'synthetic@163.com',
          'SMTP_AUTH_CODE':'synthetic-not-a-secret','AUTH_SECRET':'isolated-secret',
          'AUTH_EMAIL_PROVIDER':'netease_smtp'}))
        db.init_db()

    def smtp(self):
        context=Mock(); client=Mock(); context.__enter__=Mock(return_value=client)
        context.__exit__=Mock(return_value=False); client.send_message.return_value={}
        return context,client

    def test_accepted_mail_survives_quit_connection_error(self):
        context,client=self.smtp()
        context.__exit__.side_effect=smtplib.SMTPServerDisconnected('synthetic QUIT failure')
        with patch.object(mail,'SMTP_SSL',return_value=context):
            mail._deliver_smtp('recipient@example.invalid','synthetic','test')
        client.send_message.assert_called_once()

    def test_accepted_reminder_is_not_marked_uncertain_on_quit_failure(self):
        context,client=self.smtp()
        context.__exit__.side_effect=OSError('synthetic shutdown failure')
        with patch.object(mail,'SMTP_SSL',return_value=context):
            mail._deliver_smtp('recipient@example.invalid','synthetic','test','isolated-ref')
        client.send_message.assert_called_once()

    def test_definite_recipient_rejection_is_retryable_failure(self):
        context,client=self.smtp()
        client.send_message.side_effect=smtplib.SMTPRecipientsRefused({'recipient@example.invalid':(450,b'temporary')})
        with patch.object(mail,'SMTP_SSL',return_value=context),self.assertRaises(HTTPException):
            mail._deliver_smtp('recipient@example.invalid','synthetic','test','isolated-ref')
        client.send_message.assert_called_once()

    def test_timeout_during_submission_is_uncertain_without_resend(self):
        context,client=self.smtp(); client.send_message.side_effect=TimeoutError('synthetic DATA timeout')
        with patch.object(mail,'SMTP_SSL',return_value=context),self.assertRaises(mail.EmailDeliveryUncertain):
            mail._deliver_smtp('recipient@example.invalid','synthetic','test','isolated-ref')
        client.send_message.assert_called_once()

    def test_delayed_older_request_does_not_consume_new_code(self):
        current=[2_000_000_000]; newer={}; nested_started=[False]
        def delivery(email,code,challenge):
            if not nested_started[0]:
                nested_started[0]=True
                current[0]+=61
                newer.update(mail.request_code(email,'synthetic-client'))
        with patch.object(mail,'now',side_effect=lambda:current[0]),patch.object(mail,'send_email',side_effect=delivery):
            older=mail.request_code('recipient@example.invalid','synthetic-client')
        with closing(db.get_connection()) as con:
            consumed={r['challenge_id']:r['consumed'] for r in con.execute('SELECT challenge_id,consumed FROM auth_codes')}
        self.assertEqual(consumed[newer['challenge_id']],0)
        self.assertEqual(consumed[older['challenge_id']],1)

    def test_unknown_resets_have_separate_limits_and_do_not_consume_mail_budget(self):
        with patch.object(mail,'send_reset_email') as reset_mail,patch.object(mail,'send_email') as register_mail:
            for index in range(10):
                result=mail.request_code(f'unknown-{index}@example.invalid','synthetic-client',purpose='reset')
                self.assertIn('challenge_id',result)
            with closing(db.get_connection()) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM auth_codes').fetchone()[0],0)
                self.assertEqual(con.execute('SELECT COUNT(*) FROM unknown_reset_attempts').fetchone()[0],10)
            mail.request_code('new-user@example.invalid','synthetic-client')
        reset_mail.assert_not_called();register_mail.assert_called_once()

    def test_repeated_unknown_reset_is_rate_limited_without_a_stored_code(self):
        mail.request_code('same-unknown@example.invalid','synthetic-client',purpose='reset')
        with self.assertRaises(HTTPException) as error:
            mail.request_code('same-unknown@example.invalid','synthetic-client',purpose='reset')
        self.assertEqual(error.exception.status_code,429)
        with closing(db.get_connection()) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM auth_codes').fetchone()[0],0)


class ImageBoundaries(unittest.TestCase):
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        self.folder=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.dict(os.environ,{'MHP_IMAGE_API_KEY':'synthetic-placeholder',
          'MHP_IMAGE_BASE_URL':image.ENDPOINT}))
        self.input=self.folder/'synthetic.png';Image.new('RGB',(32,48),'blue').save(self.input)

    def response(self,dimensions):
        buffer=io.BytesIO();Image.new('RGB',dimensions,'blue').save(buffer,format='PNG')
        opener=Mock();opener.open.return_value=io.BytesIO(json.dumps({'data':[{
          'b64_json':base64.b64encode(buffer.getvalue()).decode()}]}).encode())
        return opener

    def test_wrong_native_dimensions_fail_without_resubmission(self):
        opener=self.response((32,48))
        with patch('app.services.curl_transport.build_opener',return_value=opener),self.assertRaises(image.ProviderError):
            image.edit_image('synthetic',[self.input],(1536,2048),'low')
        opener.open.assert_called_once()

    def test_native_image_is_accepted(self):
        opener=self.response((1536,2048))
        with patch('app.services.curl_transport.build_opener',return_value=opener):
            result=image.edit_image('synthetic',[self.input],(1536,2048),'low')
        with Image.open(io.BytesIO(result['image_bytes'])) as output:self.assertEqual(output.size,(1536,2048))
        opener.open.assert_called_once()


class CreditMessages(unittest.TestCase):
    def test_empty_wallet_does_not_direct_users_to_removed_purchase(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(db,'DB_PATH',Path(folder)/'synthetic.db'):
            db.init_db()
            with closing(db.get_connection()) as con,con:
                credit_service.ensure_wallet(con,'synthetic-user')
                con.execute('UPDATE credit_grants SET remaining=0')
                with self.assertRaises(HTTPException) as error:
                    credit_service.reserve_credit(con,'synthetic-user','synthetic-generation')
            self.assertEqual(error.exception.status_code,402)
            self.assertNotIn('开通会员',error.exception.detail)


class PaymentBoundaries(unittest.TestCase):
    """Internal, explicitly synthetic ledger fixtures; never submit payment notifications."""
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        folder=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(db,'DB_PATH',folder/'synthetic-ledger.db'))
        stack.enter_context(patch.dict(os.environ,{'ALIPAY_ENABLED':'0'}))
        db.init_db()
        with closing(db.get_connection()) as con,con:
            con.execute("INSERT INTO users VALUES ('synthetic-user','synthetic@example.invalid','Synthetic QA',0)")

    def order(self,key='synthetic-request'):
        return membership.create_order('synthetic-user','day',key,'synthetic-app','synthetic-seller')

    def ledger_fixture(self,order):
        return {'out_trade_no':order['order_id'],'trade_no':'synthetic-transaction',
                'total_amount':'4.90','app_id':'synthetic-app','seller_id':'synthetic-seller',
                'trade_status':'TRADE_SUCCESS'}

    def test_repeated_creation_reuses_unpaid_order_and_server_price(self):
        first=self.order();second=self.order('synthetic-new-tab')
        self.assertEqual(first['order_id'],second['order_id'])
        self.assertEqual(first['price_fen'],490)
        self.assertEqual(first['credits'],10)

    def test_duplicate_ledger_application_does_not_duplicate_entitlement(self):
        data=self.ledger_fixture(self.order())
        membership.apply_verified_payment(data);membership.apply_verified_payment(data)
        self.assertEqual(credit_service.summary('synthetic-user')['available'],15)
        with closing(db.get_connection()) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM credit_grants WHERE source='membership'").fetchone()[0],1)

    def test_amount_mismatch_does_not_grant_credits(self):
        order=self.order();data=self.ledger_fixture(order);data['total_amount']='4.91'
        with self.assertRaises(HTTPException):membership.apply_verified_payment(data)
        self.assertEqual(membership.get_order('synthetic-user',order['order_id'])['status'],'pending')
        self.assertEqual(credit_service.summary('synthetic-user')['available'],5)

    def test_full_refund_and_old_success_do_not_restore_entitlements(self):
        data=self.ledger_fixture(self.order());membership.apply_verified_payment(data)
        membership.apply_verified_payment({**data,'trade_status':'TRADE_CLOSED'})
        membership.apply_verified_payment(data)
        self.assertEqual(credit_service.summary('synthetic-user')['available'],5)
        self.assertFalse(credit_service.summary('synthetic-user')['membership']['active'])

    def test_closed_channel_rejects_order_creation_without_mutation(self):
        from app.api import auth,account
        from support_client import Client
        app=FastAPI();app.include_router(account.router)
        app.dependency_overrides[auth.require_user]=lambda:{'user_id':'synthetic-user'}
        status,_=Client(app).call('POST','/api/account/orders',{'plan_id':'day','request_id':'synthetic-closed'})
        self.assertEqual(status,503);self.assertFalse(alipay_service.ready())
        with closing(db.get_connection()) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM membership_orders').fetchone()[0],0)


if __name__=='__main__':unittest.main(verbosity=2)
