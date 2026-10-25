"""Offline acceptance tests. Never import app.main or contact a real website."""
from contextlib import ExitStack, closing
from pathlib import Path
import io
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from PIL import Image

from app.api import auth, assets, library, mkhp
from app.models import db
from app.services import storage_service, library_service
from app.services.product_reader import parse_product
from app.services.public_web import normalize_url, fetch_public
from support_client import Client


class ParserTests(unittest.TestCase):
    def test_structured_fields_and_separate_package_dimensions(self):
        data = {'@type': 'Product', 'name': 'Wood desk', 'material': 'Wood',
                'offers': {'price': 0, 'priceCurrency': 'USD'}, 'size': '100 x 60 cm',
                'additionalProperty': [{'name': 'package dimensions', 'value': '110 x 70 x 12 cm'}],
                'image': ['/desk.webp', '/desk.webp', 'http://localhost/no.png']}
        result = parse_product('<script type="application/ld+json">'+json.dumps(data)+'</script>', 'https://shop.example/p/1')
        self.assertEqual(result['fields']['price']['value'], '0')
        self.assertEqual(result['fields']['package_size']['value'], '110 x 70 x 12 cm')
        self.assertEqual(result['fields']['size']['value'], '100 x 60 cm')
        self.assertEqual(result['image_urls'], ['https://shop.example/desk.webp'])

    def test_missing_fields_are_not_invented(self):
        value = parse_product('<h1>Cup</h1><p>A beautiful product</p>', 'https://shop.example/cup')
        self.assertEqual(value['fields']['name']['value'], 'Cup')
        for key in ('price', 'size', 'package_size', 'material'):
            self.assertIn(key, value['missing_fields'])
            self.assertNotIn(key, value['fields'])

    def test_table_evidence_and_bad_json(self):
        html = '<script type="application/ld+json">broken</script><table><tr><td>包裹尺寸</td><td>20 × 10 cm</td></tr><tr><td>材质</td><td>木材</td></tr></table>'
        value = parse_product(html, 'https://shop.example/item')
        self.assertEqual(value['fields']['package_size']['value'], '20 × 10 cm')
        self.assertEqual(value['fields']['material']['value'], '木材')

    def test_private_dns_is_rejected_before_connect(self):
        for address in ('127.0.0.1', '169.254.169.254', '10.0.0.1', '::1'):
            with patch('socket.getaddrinfo', return_value=[(0, 0, 0, '', (address, 443))]), patch('socket.create_connection') as connect:
                with self.assertRaises(ValueError):
                    fetch_public('https://shop.example/x', limit=100)
                connect.assert_not_called()
        for url in ('file:///etc/passwd', 'http://a:b@shop.example/', 'http://localhost/', 'https://shop.example:9000/'):
            with self.assertRaises(ValueError):
                normalize_url(url)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack(); self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(db, 'DB_PATH', self.root/'test.db'))
        for module in (storage_service, library_service, library, mkhp, assets):
            stack.enter_context(patch.object(module, 'UPLOAD_DIR', self.root/'uploads'))
        stack.enter_context(patch('socket.create_connection', side_effect=AssertionError('Offline test only')))
        db.init_db()
        self.user = {'user_id': 'owner', 'email': 'owner@example.invalid'}
        app = FastAPI()
        for module in (assets, library, mkhp):
            app.include_router(module.router)
        app.dependency_overrides[auth.require_user] = lambda: self.user
        self.client = Client(app)

    def test_folder_import_preview_trash_restore_and_tenant_isolation(self):
        status, folder = self.client.call('POST', '/api/library/folders', {'name': 'My examples'})
        self.assertEqual(status, 201, folder)
        self.assertTrue((self.root/'uploads'/'references'/folder['folder_id']).is_dir())
        source = 'https://item.taobao.com/item.htm?id=123456'
        image = io.BytesIO(); Image.new('RGB', (50, 70), 'red').save(image, 'PNG')
        html = b'<script type="application/ld+json">{"@type":"Product","name":"Cup","image":"/cup.png"}</script>'
        def fake_fetch(url, **kwargs):
            return (html, 'text/html; charset=utf-8', source) if url == source else (image.getvalue(), 'image/png', url)
        with patch.object(mkhp, 'fetch_public', side_effect=fake_fetch):
            status, task = self.client.call('POST', '/api/mkhp/browser-imports', {
                'request_id':'synthetic-library-test','source_url':source,'confirm_import':True,
                'fields':{'name':{'value':'Cup'}},'image_urls':['https://img.alicdn.com/cup.png']})
        self.assertEqual(status, 202, task)
        task = self.client.call('GET', '/api/mkhp/imports/'+task['import_id'])[1]
        self.assertEqual(task['status'], 'completed', task)
        self.assertEqual(len(task['result']['images']), 1, task)
        iid, fid = task['import_id'], task['folder_id']
        asset = task['result']['images'][0]['asset_id']
        self.assertEqual(self.client.call('GET', '/api/assets/'+asset+'/preview')[0], 200)
        files = list((self.root/'uploads'/'references'/fid).glob('*.png'))
        self.assertEqual(len(files), 1)
        self.assertEqual(self.client.call('GET', '/api/library/folders/'+fid+'/assets')[1]['total'], 1)
        self.assertEqual(self.client.call('GET', '/api/assets?role=product')[1]['total'], 0)
        self.assertEqual(self.client.call('GET', '/api/assets?role=reference')[1]['total'], 1)
        self.user['user_id'] = 'other'
        for path in ('/api/mkhp/imports/'+iid, '/api/library/folders/'+fid+'/assets', '/api/assets/'+asset+'/preview'):
            self.assertEqual(self.client.call('GET', path)[0], 404)
        self.user['user_id'] = 'owner'
        self.assertEqual(self.client.call('DELETE', '/api/assets/'+asset)[0], 200)
        self.assertEqual(self.client.call('GET', '/api/library/folders/'+fid+'/assets')[1]['total'], 0)
        self.assertEqual(self.client.call('GET', '/api/mkhp/imports/'+iid)[1]['result']['removed_image_count'], 1)
        self.assertEqual(self.client.call('POST', '/api/assets/'+asset+'/restore', {})[0], 200)
        self.assertEqual(self.client.call('GET', '/api/assets/'+asset+'/preview')[0], 200)

    def test_source_folders_reuse_same_url_and_separate_other_urls(self):
        a = library_service.folder_for_source('owner', 'https://shop.example/a', 'A')
        self.assertEqual(a['folder_id'], library_service.folder_for_source('owner', 'https://shop.example/a', 'A')['folder_id'])
        self.assertNotEqual(a['folder_id'], library_service.folder_for_source('owner', 'https://shop.example/b', 'B')['folder_id'])

    def test_all_recognized_images_can_be_archived_in_batches_and_failures_retried(self):
        # Existing static-import history remains usable after new static imports retire.
        source='https://shop.example/many'
        images=[f'https://shop.example/{i}.png' for i in range(21)]
        html=('<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'Many','image':images})+'</script>').encode()
        data=io.BytesIO();Image.new('RGB',(10,10),'red').save(data,'PNG')
        fail=True
        def fake_fetch(url,**kwargs):
            if url==source:return html,'text/html',source
            if url==images[0] and fail:raise ValueError('Simulated download failure')
            return data.getvalue(),'image/png',url
        with patch.object(mkhp,'fetch_public',side_effect=fake_fetch):
            iid='f'*32
            folder=library_service.folder_for_source('owner',source,'Synthetic legacy import')
            result={'fields':{'name':{'value':'Many'}},'image_urls':images,'images':[],'image_errors':[],'missing_fields':[],'warnings':[]}
            stamp=library_service.now()
            with closing(db.get_connection()) as con,con:
                con.execute('INSERT INTO product_imports VALUES (?,?,?,?,?,?,?,?,?)',
                    (iid,'owner',source,folder['folder_id'],'completed',json.dumps(result),None,stamp,stamp))
            path='/api/mkhp/imports/'+iid
            self.assertEqual(self.client.call('POST',path+'/images',{'confirm_fetch':True})[0],202)
            result=self.client.call('GET',path)[1]['result']
            self.assertEqual(len(result['images']),19);self.assertEqual(result['remaining_images'],1)
            self.assertEqual(self.client.call('POST',path+'/images',{})[0],400)
            self.assertEqual(self.client.call('POST',path+'/images',{'confirm_fetch':True})[0],202)
            result=self.client.call('GET',path)[1]['result']
            self.assertEqual(len(result['images']),20);self.assertEqual(result['remaining_images'],0)
            fail=False
            self.assertEqual(self.client.call('POST',path+'/images',{'confirm_fetch':True,'retry_failed':True})[0],202)
            result=self.client.call('GET',path)[1]['result']
            self.assertEqual(len(result['images']),21);self.assertEqual(result['image_errors'],[])
            self.assertEqual(self.client.call('POST',path+'/images',{'confirm_fetch':True})[0],409)
            self.user['user_id']='other'
            self.assertEqual(self.client.call('POST',path+'/images',{'confirm_fetch':True})[0],404)

    def test_migration_is_idempotent_and_preserves_existing_rows(self):
        folder = self.client.call('POST', '/api/library/folders', {'name':'Keep'})[1]
        db.init_db()
        self.assertEqual(self.client.call('GET', '/api/library/folders')[1]['items'][0]['folder_id'], folder['folder_id'])

    def test_retired_static_import_returns_410_without_fetching(self):
        with patch.object(mkhp, 'fetch_public') as fetch:
            for confirmed in (False,True):
                self.assertEqual(self.client.call('POST', '/api/mkhp/imports', {'url':'https://shop.example/p','confirm_fetch':confirmed})[0], 410)
            fetch.assert_not_called()

    def test_migration_upgrades_old_database_without_changing_original_asset(self):
        old_path = self.root/'old.db'
        with closing(sqlite3.connect(old_path)) as con, con:
            con.execute('CREATE TABLE assets(asset_id TEXT PRIMARY KEY,filename TEXT UNIQUE NOT NULL,width INTEGER,height INTEGER,format TEXT,size_bytes INTEGER,created_at TEXT)')
            con.execute('INSERT INTO assets VALUES (?,?,?,?,?,?,?)', ('a'*32,'original.png',20,30,'PNG',100,'2026-01-01'))
        with patch.object(db,'DB_PATH',old_path):
            db.init_db()
            with closing(db.get_connection()) as con:
                row = dict(con.execute('SELECT * FROM assets').fetchone())
                self.assertEqual(row['filename'], 'original.png')
                self.assertEqual(row['width'], 20)
                self.assertEqual(row['role'], 'product')
                self.assertIsNone(row['folder_id'])
                self.assertIsNone(row['deleted_at'])
                self.assertIsNotNone(con.execute("SELECT name FROM sqlite_master WHERE name='research'").fetchone())


if __name__ == '__main__':
    unittest.main()
