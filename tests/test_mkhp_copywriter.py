import io
import json
import os
from contextlib import ExitStack, closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fastapi import FastAPI

from app.api import auth, product_drafts
from app.models import db
from app.services import copywriter
from app.services.library_service import now
from app.services.product_document import build_docx
from support_client import Client


def sample_content():
    return {'title':{'target':'Wooden desk','zh':'木质书桌'},
            'sections':[{'heading':{'target':'Product details','zh':'商品详情'},
                         'body':{'target':'The desk is made of wood.','zh':'这款书桌由木材制成。'},
                         'fact_keys':['name','material']}],
            'selling_points':[{'target':'Wood material','zh':'木质材质'}],
            'image_prompt_en':'Place the original product on a clean studio background with soft side lighting. Preserve shape, colors, logo, labels and structure. Leave space for a separate headline.',
            'image_prompt_zh':'将原商品置于整洁的影棚背景中，使用柔和侧光。保留形状、颜色、标识、标签和结构，留出空间供后续添加标题。',
            'negative_prompt_en':'No product changes, invented accessories, text or watermarks.',
            'notes_zh':['商品及包裹尺寸尚未识别，请发布前核对。']}


class CopywriterTests(unittest.TestCase):
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        self.root=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(db,'DB_PATH',self.root/'test.db'))
        stack.enter_context(patch.dict(os.environ,{'MHP_TEXT_BASE_URL':copywriter.ENDPOINT,
            'MHP_TEXT_API_KEY':'offline-test-placeholder','MHP_TEXT_MODELS':'chosen-test-model',
            'MHP_TEXT_TOKEN_PARAMETER':'max_completion_tokens'}))
        stack.enter_context(patch('socket.create_connection',side_effect=AssertionError('Network forbidden in offline tests')))
        db.init_db()
        self.user={'user_id':'owner','email':'owner@example.invalid'}
        self.import_id='a'*32
        self.fields={'name':{'value':'Wooden desk','evidence':'JSON-LD'},'material':{'value':'Wood','evidence':'JSON-LD'}}
        with closing(db.get_connection()) as con, con:
            con.execute('INSERT INTO product_imports VALUES (?,?,?,?,?,?,?,?,?)',
                        (self.import_id,'owner','https://shop.example/desk',None,'completed',json.dumps({'fields':self.fields}),None,now(),now()))
        app=FastAPI();app.include_router(product_drafts.router)
        app.dependency_overrides[auth.require_user]=lambda:self.user
        self.client=Client(app)
        self.payload={'import_id':self.import_id,'request_id':'offline-1','model':'chosen-test-model','language':'en','requirements':'柔和侧光，右侧留白','confirm_send':True}

    def generate(self):
        with patch.object(copywriter,'generate',return_value=(sample_content(),{'total_tokens':123})) as generate:
            status,value=self.client.call('POST','/api/mkhp/drafts',self.payload)
        self.assertEqual(status,200,value)
        self.assertEqual(value['status'],'completed',value)
        return value,generate

    def test_no_key_or_model_defaults(self):
        with patch.dict(os.environ,{'MHP_TEXT_API_KEY':'','MHP_TEXT_MODELS':''}):
            value=self.client.call('GET','/api/mkhp/ai-capabilities')[1]
            self.assertFalse(value['configured']);self.assertEqual(value['models'],[])
            self.assertNotIn('API_KEY',json.dumps(value))
            self.assertEqual(self.client.call('POST','/api/mkhp/drafts',self.payload)[0],503)

    def test_requires_explicit_consent_language_and_allowed_model(self):
        with patch.object(copywriter,'generate') as generate:
            for change,expected in (({'confirm_send':False},400),({'language':'xx'},400),({'model':'other'},503)):
                self.assertEqual(self.client.call('POST','/api/mkhp/drafts',{**self.payload,**change})[0],expected)
            generate.assert_not_called()

    def test_bilingual_draft_is_persisted_and_request_is_idempotent(self):
        with patch.object(copywriter,'generate',return_value=(sample_content(),{'total_tokens':123})) as generate:
            one=self.client.call('POST','/api/mkhp/drafts',self.payload)[1]
            two=self.client.call('POST','/api/mkhp/drafts',self.payload)[1]
            self.assertEqual(one['draft_id'],two['draft_id']);generate.assert_called_once()
            self.assertEqual(self.client.call('POST','/api/mkhp/drafts',{**self.payload,'requirements':'different'})[0],409)
        self.assertEqual(one['content']['sections'][0]['body']['zh'],'这款书桌由木材制成。')
        listing=self.client.call('GET','/api/mkhp/drafts?import_id='+self.import_id)[1]
        self.assertEqual(len(listing['items']),1)

    def test_failure_is_saved_without_automatic_retry_or_export(self):
        with patch.object(copywriter,'generate',side_effect=copywriter.ProviderError('HTTP 403; no retry')) as generate:
            value=self.client.call('POST','/api/mkhp/drafts',self.payload)[1]
            again=self.client.call('POST','/api/mkhp/drafts',self.payload)[1]
            self.assertEqual(value['status'],'failed');self.assertEqual(value['draft_id'],again['draft_id']);generate.assert_called_once()
        self.assertEqual(self.client.call('GET',f"/api/mkhp/drafts/{value['draft_id']}/export?format=docx")[0],409)

    def test_json_and_editable_word_exports_are_private(self):
        value,_=self.generate();did=value['draft_id']
        status,export=self.client.call('GET',f'/api/mkhp/drafts/{did}/export?format=json')
        self.assertEqual(status,200);self.assertEqual(export['product_evidence']['fields']['material']['value'],'Wood')
        status,content=self.client.call('GET',f'/api/mkhp/drafts/{did}/export?format=docx')
        self.assertEqual(status,200)
        with ZipFile(io.BytesIO(content)) as z:
            self.assertIsNone(z.testzip())
            for member in z.namelist():ET.fromstring(z.read(member))
            xml=z.read('word/document.xml').decode()
            self.assertIn('The desk is made of wood.',xml);self.assertIn('这款书桌由木材制成。',xml)
            self.assertNotIn('offline-test-placeholder',xml)
        self.user['user_id']='other'
        for suffix in ('','/export?format=json','/export?format=docx'):
            self.assertEqual(self.client.call('GET','/api/mkhp/drafts/'+did+suffix)[0],404)
        self.assertEqual(self.client.call('POST','/api/mkhp/drafts',self.payload)[0],404)

    def test_word_sanitizes_xml_characters_and_supports_rtl(self):
        content=sample_content();content['title']['target']='Desk & <wood>\x00'
        draft={'content':content,'language':'ar','model':'test','source_url':'https://shop.example/?a=1&b=2'}
        with ZipFile(io.BytesIO(build_docx(draft,{'fields':self.fields}))) as z:
            xml=z.read('word/document.xml');ET.fromstring(xml)
            self.assertIn(b'<w:bidi/>',xml);self.assertIn(b'&amp;',xml);self.assertNotIn(b'\x00',xml)

    def test_provider_request_uses_selected_model_and_does_not_send_secret_in_body(self):
        body={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(sample_content())}],
              'usage':{'input_tokens':8,'output_tokens':4,'untrusted':'omit'}}
        response=Mock();response.__enter__=Mock(return_value=io.BytesIO(json.dumps(body).encode()));response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        with patch('app.services.curl_transport.build_opener',return_value=opener):
            content,usage=copywriter.generate(self.fields,'en','chosen-test-model','柔和侧光')
        request=opener.open.call_args.args[0]
        sent=json.loads(request.data)
        self.assertEqual(request.full_url,copywriter.ENDPOINT+'/messages')
        self.assertEqual(request.get_header('X-api-key'),'offline-test-placeholder')
        self.assertEqual(sent['model'],'chosen-test-model');self.assertEqual(sent['max_tokens'],4096)
        self.assertIn('system',sent);self.assertNotIn('response_format',sent)
        self.assertNotIn('offline-test-placeholder',request.data.decode());self.assertEqual(usage,{'input_tokens':8,'output_tokens':4,'total_tokens':12})
        opener.open.assert_called_once();self.assertEqual(content['title']['zh'],'木质书桌')

    def test_provider_http_error_and_alternate_domain_do_not_leak_or_retry(self):
        opener=Mock();opener.open.side_effect=HTTPError('https://api.openai-next.com/v1/chat/completions',403,'secret diagnostic',{},None)
        with patch('app.services.curl_transport.build_opener',return_value=opener):
            with self.assertRaises(copywriter.ProviderError) as result:copywriter.generate(self.fields,'en','chosen-test-model','')
        self.assertIn('403',str(result.exception));self.assertNotIn('secret diagnostic',str(result.exception));opener.open.assert_called_once()
        with patch.dict(os.environ,{'MHP_TEXT_BASE_URL':'https://alternate.invalid/v1'}),patch('app.services.curl_transport.build_opener') as factory:
            with self.assertRaises(copywriter.ProviderError):copywriter.generate(self.fields,'en','chosen-test-model','')
            factory.assert_not_called()

    def test_model_output_with_unknown_facts_is_rejected(self):
        content=sample_content();content['sections'][0]['fact_keys']=['certification']
        body={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps(content)}]}
        response=Mock();response.__enter__=Mock(return_value=io.BytesIO(json.dumps(body).encode()));response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        with patch('app.services.curl_transport.build_opener',return_value=opener):
            with self.assertRaises(copywriter.ProviderError):copywriter.generate(self.fields,'en','chosen-test-model','')

    def test_native_truncation_refusal_and_redirect_do_not_retry(self):
        cases=[{'stop_reason':'max_tokens','content':[{'type':'text','text':'{}'}]},
               {'stop_reason':'end_turn','content':[{'type':'tool_use','name':'unexpected'}]}]
        for body in cases:
            response=Mock();response.__enter__=Mock(return_value=io.BytesIO(json.dumps(body).encode()));response.__exit__=Mock(return_value=False)
            opener=Mock();opener.open.return_value=response
            with patch('app.services.curl_transport.build_opener',return_value=opener),self.assertRaises(copywriter.ProviderError):
                copywriter.generate(self.fields,'en','chosen-test-model','')
            opener.open.assert_called_once()
        self.assertIsNone(copywriter.NoRedirect().redirect_request(None,None,302,None,None,None))


if __name__=='__main__':unittest.main()
