"""Offline contract and pipeline checks; never import app.main or touch live DB."""
import base64
import io
import json
import os
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from urllib.error import HTTPError
from PIL import Image
from app.services import reference_service as provider,credit_service,generation_service
from app.api import product_sets
import test_without_cutout

class ImageProviderTests(unittest.TestCase):
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        self.root=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.dict(os.environ,{'MHP_IMAGE_BASE_URL':provider.ENDPOINT,'MHP_IMAGE_API_KEY':'offline-image-placeholder'}))
        stack.enter_context(patch('socket.create_connection',side_effect=AssertionError('Offline test forbids networking')))
        self.paths=[]
        for i,color in enumerate(('red','green','blue')):
            path=self.root/f'{i}.png';Image.new('RGB',(32,48),color).save(path);self.paths.append(path)
        output=io.BytesIO();Image.new('RGB',(1536,2048),'blue').save(output,format='PNG');self.png=output.getvalue()

    def response(self,body):
        response=Mock();response.__enter__=Mock(return_value=io.BytesIO(json.dumps(body).encode()));response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response;return opener

    def test_multipart_uses_product_then_references_and_selected_quality(self):
        opener=self.response({'data':[{'b64_json':base64.b64encode(self.png).decode()}]})
        with patch('app.services.curl_transport.build_opener',return_value=opener):result=provider.edit_image('Preserve product',self.paths,(1536,2048),'high')
        self.assertEqual(result['image_bytes'],self.png)
        req=opener.open.call_args.args[0]
        self.assertEqual(req.full_url,provider.ENDPOINT+'/images/edits')
        body=req.data;self.assertEqual(body.count(b'name="image[]"'),3)
        self.assertLess(body.index(self.paths[0].read_bytes()),body.index(self.paths[1].read_bytes()))
        self.assertLess(body.index(self.paths[1].read_bytes()),body.index(self.paths[2].read_bytes()))
        self.assertIn(b'gpt-image-2',body);self.assertIn(b'\r\nhigh\r\n',body)
        self.assertNotIn(str(self.root).encode(),body);self.assertNotIn(b'offline-image-placeholder',body)
        self.assertNotIn(b'input_fidelity',body);opener.open.assert_called_once()

    def test_http_failures_and_url_only_output_do_not_retry_or_download(self):
        for body in ({'data':[{'url':'https://untrusted.invalid/a.png'}]}, {'data':[{'b64_json':'bad'}]}):
            opener=self.response(body)
            with patch('app.services.curl_transport.build_opener',return_value=opener),self.assertRaises(provider.ProviderError):
                provider.edit_image('prompt',self.paths[:1],(1536,2048),'low')
            opener.open.assert_called_once()
        opener=Mock();opener.open.side_effect=HTTPError(provider.ENDPOINT,403,'private upstream error',{},None)
        with patch('app.services.curl_transport.build_opener',return_value=opener),self.assertRaises(provider.ProviderError) as error:
            provider.edit_image('prompt',self.paths[:1],(1536,2048),'medium')
        self.assertIn('403',str(error.exception));self.assertNotIn('private upstream',str(error.exception));opener.open.assert_called_once()

    def test_configuration_input_limits_and_redirect_handler(self):
        with patch.dict(os.environ,{'MHP_IMAGE_API_KEY':''}):self.assertFalse(provider.available())
        with patch.dict(os.environ,{'MHP_IMAGE_BASE_URL':'https://alternate.invalid/v1'}):
            self.assertFalse(provider.available())
            with self.assertRaises(provider.ProviderError):provider.edit_image('prompt',self.paths,(1536,2048),'low')
        for paths,quality in (([], 'low'),(self.paths*2,'low'),(self.paths,None)):
            with patch('app.services.curl_transport.build_opener') as factory,self.assertRaises(provider.ProviderError):
                provider.edit_image('prompt',paths,(1536,2048),quality)
            factory.assert_not_called()
        self.assertIsNone(provider.NoRedirect().redirect_request(None,None,302,None,None,None))

class ImagePipelineTests(unittest.TestCase):
    setUp=test_without_cutout.WithoutCutoutTests.setUp

    def payload(self,count=1):
        return {'request_id':'image-offline','confirm_send':True,'spec':{'engine':'reference','image_quality':'medium','product_name':'Product','language':'en','resolution':'1200','count':count,
            'pages':[{'asset_id':self.aid,'kind':'main' if i==0 else 'feature','title':'PRODUCT','copy_lines':[]} for i in range(count)]}}

    def test_consent_quality_and_missing_key_do_not_reserve_credits(self):
        for change in ('consent','quality','key'):
            payload=self.payload()
            if change=='consent':payload['confirm_send']=False
            if change=='quality':payload['spec']['image_quality']=None
            with patch.object(provider,'available',return_value=change!='key'):
                status,_=self.client.call('POST','/api/product-sets',payload)
            self.assertEqual(status,503 if change=='key' else 400)
        self.assertEqual(credit_service.summary('owner')['available'],5)

    def test_success_is_local_history_owned_and_idempotent(self):
        png=io.BytesIO();Image.new('RGB',(90,120),'white').save(png,format='PNG')
        with patch.object(provider,'available',return_value=True):
            status,state=self.client.call('POST','/api/product-sets',self.payload())
            self.assertEqual(status,201,state)
            with patch.object(provider,'edit_image',return_value={'image_bytes':png.getvalue()}) as edit:
                product_sets._run_set(state['batch_id'],'owner')
                duplicate=self.client.call('POST','/api/product-sets',self.payload())[1]
                product_sets._run_set(state['batch_id'],'owner')
            edit.assert_called_once()
        self.assertEqual(duplicate['status'],'completed');row=duplicate['items'][0]
        self.assertEqual(row['model'],'gpt-image-2')
        self.assertTrue((generation_service.GENERATION_DIR/row['filename']).is_file())
        self.assertEqual(credit_service.summary('owner')['available'],4)
        self.assertEqual(len(self.client.call('GET','/api/product-sets')[1]['items']),1)
        self.user['user_id']='other';self.assertEqual(self.client.call('GET','/api/product-sets/'+state['batch_id'])[0],404)

    def test_failure_stops_remaining_pages_and_refunds_mhp_credits(self):
        with patch.object(provider,'available',return_value=True):
            status,state=self.client.call('POST','/api/product-sets',self.payload(2))
        self.assertEqual(status,201,state)
        with patch.object(provider,'edit_image',side_effect=provider.ProviderError('图像服务返回 HTTP 403；请检查权限、模型和额度，未自动重试')) as edit:
            product_sets._run_set(state['batch_id'],'owner')
        edit.assert_called_once()
        state=self.client.call('GET','/api/product-sets/'+state['batch_id'])[1]
        self.assertEqual([p['status'] for p in state['items']],['failed','cancelled'])
        self.assertIn('403',state['items'][0]['error'])
        self.assertEqual(credit_service.summary('owner')['available'],5)

    def test_cancel_before_submission_makes_no_call_and_refunds(self):
        with patch.object(provider,'available',return_value=True):
            status,state=self.client.call('POST','/api/product-sets',self.payload())
        self.assertEqual(status,201,state)
        self.assertEqual(self.client.call('POST','/api/product-sets/'+state['batch_id']+'/cancel',{})[0],200)
        with patch.object(provider,'edit_image') as edit:product_sets._run_set(state['batch_id'],'owner')
        edit.assert_not_called();self.assertEqual(credit_service.summary('owner')['available'],5)

    def test_long_mkhp_brief_validates_and_references_remain_owner_checked(self):
        payload=self.payload();payload['spec']['requirements']='Preserve the real product and use soft light. '*40
        with patch.object(provider,'available',return_value=True):
            status,state=self.client.call('POST','/api/product-sets',payload)
        self.assertEqual(status,201,state)
        self.client.call('POST','/api/product-sets/'+state['batch_id']+'/cancel',{})
        payload=self.payload();payload['request_id']='private-reference';payload['spec']['reference_ids']=['b'*32]
        with patch.object(provider,'available',return_value=True):
            status,_=self.client.call('POST','/api/product-sets',payload)
        self.assertEqual(status,404)
        self.assertEqual(credit_service.summary('owner')['available'],5)
