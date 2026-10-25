"""Offline integration: isolated SQLite/files, real routers/workers, fake providers."""
import base64
import copy
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
from contextlib import ExitStack, closing
from unittest.mock import Mock, patch
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi import FastAPI
from offline_client import TestClient
from PIL import Image
from app.models import db
from app.api import product_plans as plans, product_sets as sets
from app.api.auth import require_user
from app.repositories.asset_repo import create_asset
from app.services import product_planner as planner, storage_service, generation_service
from app.services.product_set_service import ProductSetSpec, build_instruction, render_copy


class ImmediateThread:
    def __init__(self, target, args=(), **kwargs):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


class Offline(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='offline-', dir=Path(__file__).parent)))
        for obj, key, value in [(db, 'DB_PATH', self.temp / 'test.db'),
                                (storage_service, 'UPLOAD_DIR', self.temp / 'uploads'),
                                (generation_service, 'GENERATION_DIR', self.temp / 'generations'),
                                (plans, '_workers', threading.BoundedSemaphore(2))]:
            self.stack.enter_context(patch.object(obj, key, value))
        self.stack.enter_context(patch.object(socket, 'create_connection', side_effect=AssertionError('Live network forbidden')))
        self.transport = self.stack.enter_context(patch.object(planner.curl_transport, 'build_opener', side_effect=AssertionError('Live transport forbidden')))
        self.stack.enter_context(patch.object(planner.copywriter, 'settings', return_value=('https://api.openai-next.com/v1', 'offline-key', ['offline-model'])))
        self.stack.enter_context(patch.object(planner.copywriter.curl_transport, 'available', return_value=True))
        self.stack.enter_context(patch.object(sets.provider, 'available', return_value=True))
        self.image_provider = self.stack.enter_context(patch.object(sets.provider, 'edit_image', side_effect=AssertionError('Live image provider forbidden')))
        self.stack.enter_context(patch.object(plans, 'threading', SimpleNamespace(Thread=ImmediateThread)))
        self.stack.enter_context(patch.object(sets, 'threading', SimpleNamespace(Thread=ImmediateThread)))
        db.init_db()
        with closing(db.get_connection()) as con, con:
            for user in ('alice', 'bob'):
                con.execute('INSERT INTO users VALUES (?,?,?,?)', (user, user + '@example.invalid', user, 1))
        image = io.BytesIO()
        Image.new('RGB', (240, 320), '#cb1010').save(image, 'PNG')
        self.png = image.getvalue()
        self.asset = create_asset({**storage_service.save_product_image(self.png), 'user_id': 'alice', 'role': 'reference'})
        self.aid = self.asset['asset_id']
        self.path = storage_service.UPLOAD_DIR / self.asset['filename']
        self.content = {'product_name_zh': '红色杯子', 'brief_zh': '暖色调，突出真实商品，少字主图。',
                        'pages': [{'asset_id': self.aid, 'kind': 'main', 'title': {'target': 'RED CUP', 'zh': '红色杯子'},
                                   'copy_lines': [{'target': '240 ml', 'zh': '240毫升'}],
                                   'direction_zh': '暖白背景，商品居中，保留真实外观。', 'fact_keys': ['seller_facts']}],
                        'notes_zh': ['材质未提供，不宣传材质。']}
        self.generate = self.stack.enter_context(patch.object(planner, 'generate', return_value=(self.content, {'input_tokens': 12})))
        self.app = FastAPI()
        self.app.include_router(plans.router)
        self.app.include_router(sets.router)
        self.app.dependency_overrides[require_user] = lambda: {'user_id': 'alice'}
        self.client = self.stack.enter_context(TestClient(self.app))

    def payload(self, **changes):
        return {'request_id': uuid4().hex, 'model': 'offline-model', 'language': 'en', 'count': 1,
                'image_ids': [self.aid], 'confirmed_facts': '红色杯子，240ml', 'wishes': '暖色高级，主图少字',
                'confirm_facts': True, 'confirm_send': True, **changes}

    def create(self, **changes):
        result = self.client.post('/api/product-plans', json=self.payload(**changes))
        self.assertEqual(result.status_code, 202, result.text)
        return result.json()

    def test_confirmations_and_empty_facts_make_no_calls(self):
        for changes in ({'confirm_send': False}, {'confirm_facts': False}, {'confirmed_facts': ''}):
            self.assertEqual(self.client.post('/api/product-plans', json=self.payload(**changes)).status_code, 400)
        self.generate.assert_not_called()

    def test_completion_idempotency_conflict_and_history_ownership(self):
        payload = self.payload()
        first = self.client.post('/api/product-plans', json=payload).json()
        self.assertEqual(first['status'], 'completed')
        self.assertEqual(first['content'], self.content)
        again = self.client.post('/api/product-plans', json=payload).json()
        self.assertEqual(first['plan_id'], again['plan_id'])
        self.assertEqual(self.generate.call_count, 1)
        conflict = {**payload, 'wishes': 'different'}
        self.assertEqual(self.client.post('/api/product-plans', json=conflict).status_code, 409)
        self.assertNotIn('user_id', first)
        self.assertEqual(len(self.client.get('/api/product-plans').json()['items']), 1)
        self.app.dependency_overrides[require_user] = lambda: {'user_id': 'bob'}
        self.assertEqual(self.client.get('/api/product-plans').json()['items'], [])
        self.assertEqual(self.client.get('/api/product-plans/' + first['plan_id']).status_code, 404)
        self.assertEqual(self.client.post('/api/product-plans', json=self.payload()).status_code, 404)

    def test_deleted_missing_and_escaping_images_rejected(self):
        for filename, deleted in [(self.asset['filename'], 'deleted'), ('missing.png', None), ('../outside.png', None)]:
            with closing(db.get_connection()) as con, con:
                con.execute('UPDATE assets SET filename=?,deleted_at=? WHERE asset_id=?', (filename, deleted, self.aid))
            self.assertEqual(self.client.post('/api/product-plans', json=self.payload()).status_code, 404)
        self.generate.assert_not_called()

    def test_import_facts_snapshot_and_ownership(self):
        iid = uuid4().hex
        with closing(db.get_connection()) as con, con:
            con.execute('INSERT INTO product_imports (import_id,user_id,source_url,status,result_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                        (iid, 'alice', 'https://example.invalid/private', 'completed', json.dumps({'fields': {'name': {'value': '杯子', 'evidence': 'private-cookie'}}}), 'now', 'now'))
        job = self.create(import_id=iid)
        self.assertEqual(job['request']['facts']['name'], '杯子')
        self.assertNotIn('private-cookie', json.dumps(self.generate.call_args.args[0]))
        self.assertNotIn('https://example.invalid', json.dumps(job))
        self.assertEqual(self.client.post('/api/product-plans', json=self.payload(import_id=uuid4().hex)).status_code, 404)
        self.app.dependency_overrides[require_user] = lambda: {'user_id': 'bob'}
        with self.assertRaises(Exception):
            plans._fields(plans.PlanRequest(**self.payload(import_id=iid)), 'bob')

    def test_edit_requires_confirmation_and_never_calls_provider(self):
        job = self.create()
        route = '/api/product-plans/' + job['plan_id']
        edited = copy.deepcopy(self.content)
        edited['pages'][0]['title']['target'] = 'YOUR RED CUP'
        self.assertEqual(self.client.put(route, json={'content': edited}).status_code, 400)
        response = self.client.put(route, json={'content': edited, 'confirm_save': True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['content'], edited)
        edited['pages'][0]['asset_id'] = uuid4().hex
        self.assertEqual(self.client.put(route, json={'content': edited, 'confirm_save': True}).status_code, 400)
        self.assertEqual(self.generate.call_count, 1)

    def test_failure_is_durable_and_not_retried(self):
        self.generate.side_effect = planner.ProviderError('模拟失败，未自动重试')
        payload = self.payload()
        first = self.client.post('/api/product-plans', json=payload).json()
        self.assertEqual(first['status'], 'failed')
        self.client.post('/api/product-plans', json=payload)
        plans.recover_plans()
        self.assertEqual(self.generate.call_count, 1)

    def test_pending_recovery_and_thread_start_failure(self):
        with patch.object(plans.threading, 'Thread'):
            pending = self.create()
            self.assertEqual(pending['status'], 'pending')
            self.assertEqual(self.client.post('/api/product-plans', json=self.payload()).status_code, 409)
        plans.recover_plans()
        recovered = self.client.get('/api/product-plans/' + pending['plan_id']).json()
        self.assertEqual(recovered['status'], 'failed')
        self.assertIn('可能已计费', recovered['error'])
        with patch.object(plans.threading, 'Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('offline')
            self.assertEqual(self.create()['status'], 'failed')
        self.generate.assert_not_called()

    def test_invalid_generated_references_and_language_are_not_saved(self):
        for key in ('asset', 'fact', 'count', 'language'):
            bad = copy.deepcopy(self.content)
            changes = {}
            if key == 'asset': bad['pages'][0]['asset_id'] = uuid4().hex
            if key == 'fact': bad['pages'][0]['fact_keys'] = ['unknown_claim']
            if key == 'count': changes['count'] = 2
            if key == 'language': changes['language'] = 'ru'
            self.generate.return_value = bad, {}
            self.assertEqual(self.create(**changes)['status'], 'failed')

    def test_authentication_and_unconfigured_model(self):
        self.assertEqual(self.client.post('/api/product-plans', json=self.payload(model='unknown')).status_code, 503)
        self.app.dependency_overrides.clear()
        self.assertEqual(self.client.get('/api/product-plans').status_code, 401)
        self.generate.assert_not_called()

    def test_multimodal_payload_and_bilingual_validation(self):
        # Bypass only our high-level fake; exercise the actual adapter with a fake opener.
        real_generate = planner_generate
        captured = []
        response = {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(self.content)}], 'usage': {'input_tokens': 9, 'secret': 'discarded'}}

        class Opener:
            def open(inner, request, timeout):
                captured.append((request, timeout))
                return io.BytesIO(json.dumps(response).encode())

        with patch.object(planner.curl_transport, 'build_opener', return_value=Opener()):
            result, usage = real_generate({'seller_facts': '240ml'}, 'en', 'offline-model', '暖色', {self.aid: self.path}, 1)
        self.assertEqual(result, self.content)
        self.assertEqual(usage, {'input_tokens': 9})
        self.assertEqual(len(captured), 1)
        request, timeout = captured[0]
        self.assertTrue(request.full_url.endswith('/messages'))
        payload = json.loads(request.data)
        self.assertNotIn(str(self.path), request.data.decode())
        blocks = payload['messages'][0]['content']
        image = Image.open(io.BytesIO(base64.b64decode(blocks[1]['source']['data'])))
        self.assertEqual(image.format, 'JPEG')
        self.assertLessEqual(max(image.size), 1600)
        self.assertEqual(json.loads(blocks[-1]['text'])['selected_images'], [self.aid])
        self.assertIn('output_schema', blocks[-1]['text'])
        self.assertEqual(timeout, 120)

    def test_transport_error_no_retry_and_safe_message(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError('https://offline.invalid', 400, 'sensitive provider body', {}, None)
        with patch.object(planner.curl_transport, 'build_opener', return_value=opener):
            with self.assertRaises(planner.ProviderError) as error:
                planner_generate({'seller_facts': 'cup'}, 'en', 'offline-model', 'warm', {self.aid: self.path}, 1)
        self.assertIn('HTTP 400', str(error.exception))
        self.assertNotIn('sensitive', str(error.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_image_resize_alpha_and_invalid_image_preflight(self):
        large = self.temp / 'large.png'
        Image.new('RGBA', (2400, 1200), (20, 40, 60, 0)).save(large)
        block = planner.image_block(large)
        with Image.open(io.BytesIO(base64.b64decode(block['source']['data']))) as image:
            self.assertEqual(image.size, (1600, 800))
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
        with self.assertRaises(planner.ProviderError):
            planner_generate({'seller_facts': 'cup'}, 'en', 'offline-model', 'warm', {self.aid: self.temp / 'missing'}, 1)
        self.transport.assert_not_called()

    def spec(self, mode='model', **changes):
        return {'product_name': '杯子', 'engine': 'reference', 'language': 'en', 'count': 1, 'resolution': '1200',
                'image_quality': 'low', 'text_rendering': mode,
                'pages': [{'asset_id': self.aid, 'kind': 'main', 'title': 'RED CUP', 'title_zh': '红杯',
                           'copy_lines': ['240 ml'], 'copy_lines_zh': ['240毫升']}], **changes}

    def test_typography_modes_validate_prompt_and_legacy(self):
        for mode in (None, 'model'):
            spec = self.spec(mode, **({'engine': 'local'} if mode == 'model' else {}))
            result = self.client.post('/api/product-sets', json={'request_id': uuid4().hex, 'spec': spec, 'confirm_send': True})
            self.assertEqual(result.status_code, 400, result.text)
        spec = self.spec()
        spec.pop('text_rendering')
        self.assertEqual(ProductSetSpec(**spec).text_rendering, 'local')
        model_prompt = build_instruction(ProductSetSpec(**self.spec('model')), 0)
        local_prompt = build_instruction(ProductSetSpec(**self.spec('local')), 0)
        self.assertIn('EXACT approved', model_prompt)
        self.assertIn('RED CUP', model_prompt)
        self.assertNotIn('红杯', model_prompt)
        self.assertNotIn('Leave upper 27%', model_prompt)
        self.assertIn('Leave upper 27%', local_prompt)
        clean = self.spec('model')
        clean['pages'][0]['no_overlay'] = True
        self.assertNotIn('EXACT approved', build_instruction(ProductSetSpec(**clean), 0))

    def test_both_typography_modes_through_generation_worker(self):
        self.image_provider.side_effect = None
        self.image_provider.return_value = {'image_bytes': self.png}
        for mode in ('model', 'local'):
            payload = {'request_id': uuid4().hex, 'spec': self.spec(mode), 'confirm_send': True}
            result = self.client.post('/api/product-sets', json=payload)
            self.assertEqual(result.status_code, 201, result.text)
            state = result.json()
            self.assertEqual(state['status'], 'completed', state)
            item = state['items'][0]
            self.assertEqual(item['workflow']['text_rendering'], mode)
            with Image.open(generation_service.GENERATION_DIR / item['filename']) as image:
                self.assertEqual(image.size, (900, 1200))
                self.assertEqual(image.getpixel((0, 0)), (203, 16, 16) if mode == 'model' else (246, 249, 253))
            self.client.post('/api/product-sets', json=payload)
        self.assertEqual(self.image_provider.call_count, 2)
        self.generate.assert_not_called()

    def test_screenshot_main_copy_survives_plan_edit_and_image_prompt(self):
        pairs = [
            ('8 уровней температуры', '八档调温'),
            ('Таймер 4/8/12 ч', '4/8/12小时定时'),
            ('Водонепроницаемый и огнестойкий', '防水阻燃'),
            ('30 × 35 см', '30×35厘米'),
        ]
        content = copy.deepcopy(self.content)
        page = content['pages'][0]
        page['title'] = {'target': 'КОВРИК С ПОДОГРЕВОМ ДЛЯ ПИТОМЦЕВ', 'zh': '宠物加热垫'}
        page['copy_lines'] = [{'target': target, 'zh': zh} for target, zh in pairs]
        self.generate.return_value = content, {}
        job = self.create(language='ru', confirmed_facts='宠物加热垫；八档调温；4/8/12小时；防水阻燃；30×35cm')
        self.assertEqual(job['status'], 'completed', job)
        saved = self.client.put('/api/product-plans/' + job['plan_id'],
            json={'content': content, 'confirm_save': True})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['content']['pages'][0]['copy_lines'], page['copy_lines'])
        for mode in ('local', 'model'):
            spec = self.spec(mode, language='ru')
            spec['pages'][0].update(title=page['title']['target'], title_zh=page['title']['zh'],
                copy_lines=[p[0] for p in pairs], copy_lines_zh=[p[1] for p in pairs])
            parsed = ProductSetSpec(**spec)
            if mode == 'model':
                prompt = build_instruction(parsed, 0)
                for target, zh in pairs:
                    self.assertIn(target, prompt)
                    self.assertNotIn(zh, prompt)
            else:
                image = render_copy(self.path, parsed.pages[0], (900, 1200))
                self.assertEqual(image.size, (900, 1200))
            self.assertEqual(parsed.pages[0].copy_lines, [p[0] for p in pairs])
        self.image_provider.assert_not_called()


# Capture the real function before the per-test mock starts.
planner_generate = planner.generate
if __name__ == '__main__':
    unittest.main(verbosity=2)
