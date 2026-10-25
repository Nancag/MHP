"""Offline integration checks: isolated DB/files, mocked web downloads, no main import."""
import io
import json
import shutil
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi import FastAPI
from offline_client import TestClient
from PIL import Image
from app.models import db
from app.api import mkhp, library, assets
from app.api.auth import require_user
from app.services import library_service, storage_service
from app.services.storage_service import save_product_image
from app.repositories.asset_repo import create_asset
from app.api.product_sets import _assets
from types import SimpleNamespace


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='isolated-', dir=Path(__file__).parent)
        root = Path(self.temp.name)
        self.patches = [patch.object(db, 'DB_PATH', root / 'test.db'),
                        patch.object(storage_service, 'UPLOAD_DIR', root / 'uploads'),
                        patch.object(library_service, 'UPLOAD_DIR', root / 'uploads'),
                        patch.object(library, 'UPLOAD_DIR', root / 'uploads'),
                        patch.object(mkhp, 'UPLOAD_DIR', root / 'uploads'),
                        patch.object(assets, 'UPLOAD_DIR', root / 'uploads'),
                        patch.object(socket, 'create_connection', side_effect=AssertionError('No live network permitted'))]
        for item in self.patches:
            item.start()
        db.init_db()
        with closing(db.get_connection()) as con, con:
            for uid in ('alice', 'bob'):
                con.execute('INSERT INTO users VALUES (?,?,?,?)', (uid, uid + '@example.invalid', uid, 1))
        image = io.BytesIO()
        Image.new('RGB', (320, 400), 'blue').save(image, format='PNG')
        self.png = image.getvalue()
        self.app = FastAPI()
        for router in (mkhp.router, library.router, assets.router):
            self.app.include_router(router)
        self.app.dependency_overrides[require_user] = lambda: {'user_id': 'alice'}
        self.client = TestClient(self.app)
        self.fetcher = patch.object(mkhp, 'fetch_public', return_value=(self.png, 'image/png', 'https://img.alicdn.com/test.png'))
        self.fetch = self.fetcher.start()

    def tearDown(self):
        self.client.close()
        self.fetcher.stop()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def capture(self, product='123', request=None, confirm=True):
        return {'request_id': request or uuid4().hex, 'version': 1,
                'source_url': 'https://item.taobao.com/item.htm?id=' + product + '&tracking=ignored',
                'fields': {'name': {'value': '测试商品'}, 'material': {'value': '棉'},
                           'size': {'value': '20 x 30 cm'}, 'package_size': {'value': '25 x 35 cm'},
                           'price': {'value': '19.90'}, 'currency': {'value': 'CNY'}},
                'image_urls': ['https://img.alicdn.com/test.png'], 'confirm_import': confirm}

    def imported(self, **kwargs):
        result = self.client.post('/api/mkhp/browser-imports', json=self.capture(**kwargs))
        self.assertEqual(result.status_code, 202, result.text)
        return self.client.get('/api/mkhp/imports/' + result.json()['import_id']).json()

    def test_static_disabled_no_fetch_or_record(self):
        response = self.client.post('/api/mkhp/imports', json={'url': 'https://example.com/item', 'confirm_fetch': True})
        self.assertEqual(response.status_code, 410)
        self.fetch.assert_not_called()
        self.assertEqual(self.client.get('/api/mkhp/imports').json()['items'], [])

    def test_requires_explicit_import_confirmation(self):
        response = self.client.post('/api/mkhp/browser-imports', json=self.capture(confirm=False))
        self.assertEqual(response.status_code, 400)
        self.fetch.assert_not_called()

    def test_two_sources_are_separate_and_files_exist(self):
        a, b = self.imported(product='123'), self.imported(product='456')
        self.assertEqual(a['status'], 'completed')
        self.assertNotEqual(a['folder_id'], b['folder_id'])
        self.assertEqual(a['source_url'], 'https://item.taobao.com/item.htm?id=123')
        for item in (a, b):
            rows = self.client.get('/api/library/folders/' + item['folder_id'] + '/assets').json()
            self.assertEqual(rows['total'], 1)
            self.assertTrue(rows['items'][0]['filename'].startswith('references/' + item['folder_id'] + '/'))
            self.assertTrue((storage_service.UPLOAD_DIR / rows['items'][0]['filename']).is_file())
            self.assertEqual(item['result']['fields']['package_size']['value'], '25 x 35 cm')
        self.assertEqual(self.fetch.call_count, 2)
        self.assertTrue(all(call.args[0].endswith('.png') for call in self.fetch.call_args_list))

    def test_duplicate_request_does_not_redownload(self):
        request = uuid4().hex
        a, b = self.imported(request=request), self.imported(request=request)
        self.assertEqual(a['import_id'], b['import_id'])
        self.assertEqual(self.fetch.call_count, 1)
        changed = self.capture(request=request)
        changed['fields']['name']['value'] = '不同商品'
        self.assertEqual(self.client.post('/api/mkhp/browser-imports', json=changed).status_code, 409)

    def test_same_product_reuses_folder(self):
        a, b = self.imported(), self.imported()
        self.assertEqual(a['folder_id'], b['folder_id'])

    def test_custom_folder_upload_delete_restore(self):
        folder = self.client.post('/api/library/folders', json={'name': '我的示例图'}).json()
        uploaded = self.client.post('/api/assets', data={'role': 'reference', 'folder_id': folder['folder_id']},
                                    files={'file': ('test.png', self.png, 'image/png')})
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        aid = uploaded.json()['asset_id']
        self.assertEqual(self.client.delete('/api/assets/' + aid).status_code, 200)
        self.assertEqual(self.client.get('/api/library/folders/' + folder['folder_id'] + '/assets').json()['total'], 0)
        self.assertEqual(self.client.get('/api/assets/' + aid + '/preview').status_code, 404)
        self.assertEqual(self.client.post('/api/assets/' + aid + '/restore').status_code, 200)
        self.assertEqual(self.client.get('/api/library/folders/' + folder['folder_id'] + '/assets').json()['total'], 1)

    def test_import_deletion_updates_mkhp_and_ptmd(self):
        item = self.imported()
        aid = item['result']['images'][0]['asset_id']
        self.assertEqual(self.client.delete('/api/assets/' + aid).status_code, 200)
        updated = self.client.get('/api/mkhp/imports/' + item['import_id']).json()
        self.assertEqual(updated['result']['images'], [])
        self.assertEqual(updated['result']['removed_image_count'], 1)
        self.assertEqual(self.client.get('/api/library/folders/' + item['folder_id'] + '/assets').json()['total'], 0)

    def test_user_ownership_is_enforced(self):
        item = self.imported()
        aid = item['result']['images'][0]['asset_id']
        self.app.dependency_overrides[require_user] = lambda: {'user_id': 'bob'}
        for path in ('/api/mkhp/imports/' + item['import_id'], '/api/library/folders/' + item['folder_id'] + '/assets', '/api/assets/' + aid + '/preview'):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.delete('/api/assets/' + aid).status_code, 404)

    def test_imported_image_can_be_resolved_for_generation(self):
        item = self.imported()
        aid = item['result']['images'][0]['asset_id']
        product = create_asset({**save_product_image(self.png), 'user_id': 'alice', 'role': 'product'})
        spec = SimpleNamespace(pages=[SimpleNamespace(asset_id=product['asset_id'])], reference_ids=[aid])
        paths = _assets(spec, 'alice')
        self.assertEqual(set(paths), {aid, product['asset_id']})
        self.assertTrue(all(p.is_file() for p in paths.values()))

    def test_invalid_image_origin_and_anonymous_import_rejected(self):
        data = self.capture()
        data['image_urls'] = ['https://example.com/unknown.png']
        self.assertEqual(self.client.post('/api/mkhp/browser-imports', json=data).status_code, 422)
        self.fetch.assert_not_called()
        self.app.dependency_overrides.clear()
        self.assertEqual(self.client.post('/api/mkhp/browser-imports', json=self.capture()).status_code, 401)

    def test_helper_download_and_stale_helper_rejected(self):
        response = self.client.get('/api/mkhp/collector/installer')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'MZ'))
        root = Path(self.temp.name) / 'incomplete-helper'
        root.mkdir()
        with patch.object(mkhp, 'COLLECTOR_ROOT', root):
            self.assertEqual(self.client.get('/api/mkhp/collector/installer').status_code, 503)
        for file in mkhp.COLLECTOR_ROOT.iterdir():
            if file.is_file():
                shutil.copy2(file, root / file.name)
        with patch.object(mkhp, 'COLLECTOR_ROOT', root):
            self.assertEqual(self.client.get('/api/mkhp/collector/installer').status_code, 200)
            (root / 'extractor.js').write_text('stale source', encoding='utf-8')
            self.assertEqual(self.client.get('/api/mkhp/collector/installer').status_code, 503)


if __name__ == '__main__':
    unittest.main(verbosity=2)
