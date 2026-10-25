"""Retained original-photo layout and historical downloads without segmentation packages."""
import asyncio
import io
import json
from pathlib import Path
import tempfile
import hashlib
from contextlib import ExitStack,closing
import unittest
from unittest.mock import Mock,patch
import zipfile
from PIL import Image
from fastapi import FastAPI
from app.api import auth,assets,generations,product_sets,workspace
from app.models import db
from app.repositories.asset_repo import create_asset
from app.services import generation_service,storage_service,credit_service,fixed_ptmd_template,reference_service as provider
from support_client import Client


class WithoutCutoutTests(unittest.TestCase):
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        self.root=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(db,'DB_PATH',self.root/'test.db'))
        stack.enter_context(patch.object(storage_service,'UPLOAD_DIR',self.root/'uploads'))
        stack.enter_context(patch.object(assets,'UPLOAD_DIR',self.root/'uploads'))
        stack.enter_context(patch.object(generation_service,'GENERATION_DIR',self.root/'generated'))
        stack.enter_context(patch.object(generations,'GENERATION_DIR',self.root/'generated'))
        stack.enter_context(patch.object(product_sets,'_submit_set',Mock()))
        stack.enter_context(patch('urllib.request.urlopen',side_effect=AssertionError('No remote API allowed')))
        db.init_db()
        self.user={'user_id':'owner','email':'owner@example.invalid'}
        self.app=FastAPI()
        for module in (auth,assets,generations,product_sets,workspace):self.app.include_router(module.router)
        self.app.dependency_overrides[auth.require_user]=lambda:self.user
        self.client=Client(self.app)
        self.aid='a'*32
        storage_service.UPLOAD_DIR.mkdir()
        Image.new('RGBA',(100,150),(210,35,35,255)).save(storage_service.UPLOAD_DIR/(self.aid+'.png'))
        create_asset(dict(asset_id=self.aid,user_id='owner',filename=self.aid+'.png',width=100,height=150,format='PNG',size_bytes=100,role='product'))

    def test_cutout_routes_are_absent(self):
        for method,path,payload in (('POST','/api/cutouts',{'asset_id':self.aid}),('GET','/api/cutouts',None),('GET','/api/cutouts/'+self.aid+'/preview',None)):
            self.assertEqual(self.client.call(method,path,payload)[0],404)
        self.assertFalse(any('cutout' in path for path in self.app.openapi()['paths']))

    def test_local_set_renders_original_reviews_and_exports_without_ai(self):
        payload={'request_id':'local-original','spec':{'engine':'local','product_name':'Product','language':'en','resolution':'1200','count':1,'pages':[{'asset_id':self.aid,'kind':'main','title':'ORIGINAL PRODUCT','copy_lines':['Original material']}]}}
        status,state=self.client.call('POST','/api/product-sets',payload)
        self.assertEqual(status,201,state)
        product_sets._run_set(state['batch_id'],'owner')
        status,state=self.client.call('GET','/api/product-sets/'+state['batch_id'])
        self.assertEqual(state['status'],'completed',state)
        self.assertEqual(credit_service.summary('owner')['available'],4)
        row=state['items'][0]
        self.assertTrue((generation_service.GENERATION_DIR/row['filename']).is_file())
        payload={'product_matches':True,'copy_matches':True,'no_extra_accessories':True,'layout_matches':True}
        self.assertEqual(self.client.call('POST',f"/api/product-sets/{state['batch_id']}/pages/{row['generation_id']}/review",payload)[0],200)
        response=product_sets.download_set(state['batch_id'],self.user,1200)
        with zipfile.ZipFile(response.path) as archive:
            self.assertIn('01.png',archive.namelist())
            with Image.open(io.BytesIO(archive.read('01.png'))) as image:self.assertEqual(image.size,(900,1200))
        asyncio.run(response.background())
        self.user['user_id']='other'
        self.assertEqual(self.client.call('GET','/api/product-sets/'+state['batch_id'])[0],404)

    def test_legacy_preferences_are_filtered_and_no_models_are_advertised(self):
        with closing(db.get_connection()) as con,con:
            con.execute('INSERT INTO preferences VALUES (?,?)',('owner',json.dumps({'theme':'light','model':'old-model','clean_edges':True})))
        value=self.client.call('GET','/api/workspace/settings')[1]
        self.assertEqual(value['preferences']['theme'],'light')
        self.assertNotIn('model',value['preferences'])
        self.assertNotIn('clean_edges',value['preferences'])
        self.assertFalse(value['cutout_enabled'])
        self.assertEqual(self.client.call('PUT','/api/workspace/settings',value['preferences'])[0],200)

    def test_disabled_ai_creation_does_not_charge(self):
        before=credit_service.summary('owner')['available']
        status,value=self.client.call('POST','/api/generations',{'prompt':'test'})
        self.assertEqual(status,503,value)
        self.assertEqual(credit_service.summary('owner')['available'],before)

    def test_exact_approved_source_returns_fixed_poster_without_ai_or_credit(self):
        """The owner-approved source/output pair ignores all editable AI settings."""
        source=self.root/'approved-source.png'; target=self.root/'approved-output.png'
        Image.new('RGB',(80,80),(15,25,35)).save(source)
        Image.new('RGB',(1086,1448),(220,120,20)).save(target)
        (storage_service.UPLOAD_DIR/(self.aid+'.png')).write_bytes(source.read_bytes())
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        before=credit_service.summary('owner')['available']
        payload={'request_id':'fixed-template','confirm_send':False,'spec':{
            'engine':'reference','image_quality':None,'text_rendering':None,'product_name':'ignored',
            'requirements':'This prompt must not influence the output.', 'language':'en','resolution':'1200','count':1,
            'pages':[{'asset_id':self.aid,'kind':'main','title':'ignored','copy_lines':[]}]}}
        with patch.object(fixed_ptmd_template,'SOURCE_SHA256',digest), \
             patch.object(fixed_ptmd_template,'RESULT',target), \
             patch.object(provider,'edit_image') as ai:
            status,state=self.client.call('POST','/api/product-sets',payload)
            self.assertEqual(status,201,state)
            product_sets._run_set(state['batch_id'],'owner')
        ai.assert_not_called()
        state=self.client.call('GET','/api/product-sets/'+state['batch_id'])[1]
        row=state['items'][0]
        self.assertEqual(row['type'],'fixed_template')
        self.assertEqual(row['model'],fixed_ptmd_template.TEMPLATE_ID)
        self.assertEqual(credit_service.summary('owner')['available'],before)
        generated=generation_service.GENERATION_DIR/row['filename']
        self.assertEqual(generated.read_bytes(),target.read_bytes())
        self.assertTrue(row['workflow']['prompt_ignored'])
        self.assertEqual(row['workflow']['api_calls'],0)

    def test_segmentation_runtime_is_not_required(self):
        root=Path(__file__).resolve().parents[1]
        for relative in ('app/api/cutouts.py','app/services/cutout_service.py','data/models'):
            self.assertFalse((root/relative).exists(),relative)
        text=(root/'requirements-cloud.lock').read_text()
        for package in ('rembg==','onnxruntime==','PyMatting==','numpy=='):
            self.assertNotIn(package,text)
