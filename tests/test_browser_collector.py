import asyncio
import io
import json
from pathlib import Path
from unittest.mock import patch
import unittest
import zipfile
from PIL import Image
from app.api import mkhp
import test_mkhp_phase1

class BrowserCollectorTests(unittest.TestCase):
    setUp=test_mkhp_phase1.LibraryTests.setUp

    def payload(self):
        return {'request_id':'browser-offline','source_url':'https://item.taobao.com/item.htm?id=721469796882',
                'fields':{'name':{'value':'Test desk','evidence':'页面标题'},'material':{'value':'Wood','evidence':'材质：Wood'}},
                'image_urls':['https://img.alicdn.com/example.png'],'confirm_import':True}

    def test_browser_import_archives_once_and_keeps_owner_and_source(self):
        image=io.BytesIO();Image.new('RGB',(40,60),'blue').save(image,'PNG')
        with patch.object(mkhp,'fetch_public',return_value=(image.getvalue(),'image/png','https://img.alicdn.com/example.png')) as fetch:
            code,state=self.client.call('POST','/api/mkhp/browser-imports',self.payload())
            self.assertEqual(code,202,state)
            second=self.client.call('POST','/api/mkhp/browser-imports',self.payload())[1]
            self.assertEqual(second['import_id'],state['import_id']);fetch.assert_called_once()
        value=self.client.call('GET','/api/mkhp/imports/'+state['import_id'])[1]
        self.assertEqual(value['status'],'completed');self.assertEqual(value['result']['fields']['material']['value'],'Wood')
        self.assertIn('package_size',value['result']['missing_fields'])
        self.assertEqual(len(value['result']['images']),1)
        self.assertEqual(self.client.call('GET','/api/library/folders')[1]['items'][0]['source_url'],self.payload()['source_url'])
        changed=self.payload();changed['fields']['name']['value']='Different'
        self.assertEqual(self.client.call('POST','/api/mkhp/browser-imports',changed)[0],409)
        self.user['user_id']='other'
        self.assertEqual(self.client.call('GET','/api/mkhp/imports/'+state['import_id'])[0],404)

    def test_browser_import_rejects_missing_confirmation_and_unsafe_data(self):
        with patch.object(mkhp,'fetch_public') as fetch:
            data=self.payload();data['confirm_import']=False
            self.assertEqual(self.client.call('POST','/api/mkhp/browser-imports',data)[0],400)
            for update in ({'source_url':'http://127.0.0.1/private'},{'image_urls':['https://private.invalid/a.png']},{'cookies':'forbidden'}):
                self.assertEqual(self.client.call('POST','/api/mkhp/browser-imports',{**self.payload(),**update})[0],422)
            data=self.payload();data['fields']['password']={'value':'forbidden'}
            self.assertEqual(self.client.call('POST','/api/mkhp/browser-imports',data)[0],422)
            fetch.assert_not_called()

    def test_image_failure_preserves_facts_without_automatic_retry(self):
        with patch.object(mkhp,'fetch_public',side_effect=ValueError('图片无法公开读取')) as fetch:
            _,state=self.client.call('POST','/api/mkhp/browser-imports',self.payload())
            fetch.assert_called_once()
        value=self.client.call('GET','/api/mkhp/imports/'+state['import_id'])[1]
        self.assertEqual(value['result']['fields']['name']['value'],'Test desk')
        self.assertEqual(len(value['result']['image_errors']),1)

    def test_download_package_is_allowlisted_and_has_no_credentials_permissions(self):
        response=mkhp.download_collector()
        try:
            with zipfile.ZipFile(response.path) as archive:
                self.assertEqual(len(archive.namelist()),8)
                manifest=json.loads(archive.read('mhp-collector/manifest.json'))
                self.assertEqual(set(manifest['permissions']),{'activeTab','scripting'})
                self.assertNotIn('<all_urls>',manifest['host_permissions'])
                self.assertEqual(manifest['version'],'0.3.0')
                self.assertIn('mhp-collector/bridge.js',archive.namelist())
                self.assertIn('mhp-collector/background.js',archive.namelist())
                self.assertIn('https://118.178.92.58/*',manifest['host_permissions'])
                self.assertFalse(any('.env' in p for p in archive.namelist()))
        finally:asyncio.run(response.background())
