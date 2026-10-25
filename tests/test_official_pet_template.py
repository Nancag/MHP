"""Official heating-pad workflow using isolated data and fake paid providers."""
import copy
import hashlib
import io
import json
import unittest
from contextlib import closing
from unittest.mock import patch
from uuid import uuid4

import test_product_planner as planner_tests
from app.api import workspace
from app.models import db
from app.services import credit_service, official_templates, product_planner
from app.services.product_set_service import ProductSetSpec, build_instruction

PET = official_templates.PET_ID


class OfficialPetTemplateTests(unittest.TestCase):
    setUp = planner_tests.Offline.setUp
    payload = planner_tests.Offline.payload
    create = planner_tests.Offline.create
    spec = planner_tests.Offline.spec

    def pet_content(self, count=7):
        content = copy.deepcopy(self.content)
        content['product_name_zh'] = '宠物加热垫'
        content['pages'] = [copy.deepcopy(content['pages'][0]) for _ in range(count)]
        for index, page in enumerate(content['pages']):
            page.update(kind='main' if index == 0 else 'feature',
                        title={'target': 'КОВРИК ДЛЯ ПИТОМЦЕВ' if index == 0 else 'ДЕТАЛИ ТОВАРА', 'zh': '宠物加热垫' if index == 0 else '商品细节'},
                        copy_lines=[{'target': '30 × 35 см', 'zh': '30×35厘米'}] if index == 0 else [],
                        direction_zh='展示真实外观，不添加配件。')
        return content

    def pet_spec(self, content, mode='model'):
        return self.spec(mode, product_name='宠物加热垫', preset_id=PET, language='ru',
                         count=len(content['pages']), pages=[{
            'asset_id': p['asset_id'], 'kind': p['kind'], 'title': p['title']['target'],
            'title_zh': p['title']['zh'], 'copy_lines': [l['target'] for l in p['copy_lines']],
            'copy_lines_zh': [l['zh'] for l in p['copy_lines']], 'direction': p['direction_zh']
        } for p in content['pages']])

    def test_catalog_copy_export_import_preserves_preset_without_claims_or_assets(self):
        self.app.include_router(workspace.router)
        item = next(i for i in self.client.get('/api/workspace/template-catalog').json()['items'] if i['template_id'] == PET)
        self.assertEqual(item['verification'], 'mhp-official')
        self.assertIsNone(item['payload']['spec'])
        self.assertEqual(item['payload']['planner'], {'preset_id': PET})
        self.assertNotIn('confirmed_facts', json.dumps(item))
        response = self.client.post('/api/workspace/templates', json={k: item[k] for k in ('name', 'description', 'payload')})
        self.assertEqual(response.status_code, 201, response.text)
        exported = self.client.get('/api/workspace/templates/' + response.json()['template_id'] + '/export').json()
        self.assertEqual(exported['template']['payload']['planner']['preset_id'], PET)
        self.assertEqual(self.client.post('/api/workspace/templates/import', json=exported).status_code, 201)
        exported['template']['payload']['planner']['api_key'] = 'forbidden'
        self.assertEqual(self.client.post('/api/workspace/templates/import', json=exported).status_code, 422)
        exported['template']['payload']['planner'] = {'preset_id': 'unknown'}
        self.assertEqual(self.client.post('/api/workspace/templates/import', json=exported).status_code, 422)
        self.generate.assert_not_called()
        self.image_provider.assert_not_called()

    def test_selection_and_confirmation_reject_before_paid_work(self):
        for changes in ({'count': 6}, {'count': 1}, {'language': 'en'}, {'preset_id': 'unknown'}):
            payload = self.payload(preset_id=PET, language='ru', count=7)
            payload.update(changes)
            self.assertEqual(self.client.post('/api/product-plans', json=payload).status_code, 422)
        for changes in ({'confirm_send': False}, {'confirm_facts': False}, {'confirmed_facts': ''}):
            self.assertEqual(self.client.post('/api/product-plans', json=self.payload(preset_id=PET, language='ru', count=7, **changes)).status_code, 400)
        self.generate.assert_not_called()
        self.image_provider.assert_not_called()

    def test_789_planning_retains_canonical_id_and_does_not_generate_images(self):
        seed = copy.deepcopy(self.content)
        for count in (7, 8, 9):
            self.content = copy.deepcopy(seed)
            content = self.pet_content(count)
            self.generate.return_value = content, {}
            job = self.create(preset_id=PET, count=count, language='ru', confirmed_facts='宠物加热垫，尺寸30×35cm')
            self.assertEqual(job['status'], 'completed', job)
            self.assertEqual(job['request']['preset_id'], PET)
            self.assertEqual(self.generate.call_args.kwargs['preset_id'], PET)
            saved = self.client.put('/api/product-plans/' + job['plan_id'], json={'content': content, 'confirm_save': True})
            self.assertEqual(saved.status_code, 200, saved.text)
        self.image_provider.assert_not_called()

    def test_dimensions_in_model_output_manual_edits_and_generation_are_blocked(self):
        content = self.pet_content()
        self.generate.return_value = content, {}
        job = self.create(preset_id=PET, count=7, language='ru')
        self.assertEqual(job['status'], 'completed', job)
        for target, zh in [('30 × 35 см', '尺寸'), ('Размер 35 cm', '尺寸'), ('尺寸', '长30厘米')]:
            bad = copy.deepcopy(content)
            bad['pages'][1]['copy_lines'] = [{'target': target, 'zh': zh}]
            edited = self.client.put('/api/product-plans/' + job['plan_id'], json={'content': bad, 'confirm_save': True})
            self.assertEqual(edited.status_code, 400, edited.text)
            self.assertEqual(self.client.post('/api/product-sets', json={'request_id': uuid4().hex, 'spec': self.pet_spec(bad), 'confirm_send': True}).status_code, 422)
            self.generate.return_value = bad, {}
            self.assertEqual(self.create(preset_id=PET, count=7, language='ru')['status'], 'failed')
        self.image_provider.assert_not_called()

    def test_real_adapter_gets_rules_but_never_unverified_checklist(self):
        content = self.pet_content()
        captured = []
        response = {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(content)}]}

        class Opener:
            def open(inner, request, timeout):
                captured.append(json.loads(request.data))
                return io.BytesIO(json.dumps(response).encode())

        with patch.object(product_planner.curl_transport, 'build_opener', return_value=Opener()):
            result, _ = planner_tests.planner_generate({'seller_facts': '宠物加热垫，30×35cm'}, 'ru', 'offline-model', '温暖高级', {self.aid: self.path}, 7, preset_id=PET)
        self.assertEqual(len(result['pages']), 7)
        self.assertEqual(len(captured), 1)
        self.assertIn('尺寸仅在主图', captured[0]['system'])
        sent = json.dumps(captured, ensure_ascii=False)
        self.assertNotIn('八档调温', sent)
        self.assertNotIn('4/8/12', sent)
        self.image_provider.assert_not_called()

    def test_seven_images_both_typography_modes_review_retry_and_idempotency(self):
        content = self.pet_content()
        self.stack.enter_context(patch.object(credit_service, 'WELCOME_CREDITS', 40))
        prompts = []

        def fake_image(prompt, inputs, size, quality):
            prompts.append(prompt)
            self.assertEqual(inputs, [self.path])
            self.assertEqual(size, (1536, 2048))
            return {'image_bytes': self.png}

        self.image_provider.side_effect = fake_image
        for mode in ('model', 'local'):
            payload = {'request_id': uuid4().hex, 'spec': self.pet_spec(content, mode), 'confirm_send': True}
            response = self.client.post('/api/product-sets', json=payload)
            self.assertEqual(response.status_code, 201, response.text)
            state = response.json()
            self.assertEqual(state['status'], 'completed', state)
            self.assertEqual(len(state['items']), 7)
            for index in range(7):
                self.assertIn(f'Page {index + 1}/7', prompts[-7 + index])
                self.assertIn('MHP pet heating pad template', prompts[-7 + index])
                if index:
                    self.assertIn('Do not display any dimensions', prompts[-7 + index])
            calls = self.image_provider.call_count
            self.assertEqual(self.client.post('/api/product-sets', json=payload).json()['batch_id'], state['batch_id'])
            self.assertEqual(self.image_provider.call_count, calls)
            path = '/api/product-sets/' + state['batch_id']
            self.assertEqual(self.client.get(path + '/download').status_code, 400)
            first = state['items'][0]
            review = self.client.post(path + '/pages/' + first['generation_id'] + '/review', json={
                'product_matches': True, 'copy_matches': True, 'no_extra_accessories': True, 'layout_matches': True})
            self.assertEqual(review.status_code, 200, review.text)
            # A manually changed detail cannot evade template validation on a charged retry.
            bad = self.pet_spec(content, mode)['pages'][1]
            bad['copy_lines'] = ['30 × 35 см']
            retry = self.client.post(path + '/pages/' + state['items'][1]['generation_id'] + '/regenerate', json={'page': bad, 'confirm_send': True})
            self.assertEqual(retry.status_code, 400, retry.text)
            self.assertEqual(self.image_provider.call_count, calls)
        self.assertEqual(self.image_provider.call_count, 14)
        self.generate.assert_not_called()

    def test_new_optional_ids_preserve_historical_request_hashes(self):
        payload = self.payload()
        job = self.client.post('/api/product-plans', json=payload).json()
        from app.api.product_plans import PlanRequest
        encoded = PlanRequest(**payload).model_dump_json(exclude={'request_id', 'confirm_send', 'confirm_facts', 'preset_id'})
        with closing(db.get_connection()) as con:
            actual = con.execute('SELECT payload_hash FROM product_plans WHERE plan_id=?', (job['plan_id'],)).fetchone()[0]
        self.assertEqual(actual, hashlib.sha256(encoded.encode()).hexdigest())
        self.image_provider.side_effect = None
        self.image_provider.return_value = {'image_bytes': self.png}
        spec = self.spec()
        result = self.client.post('/api/product-sets', json={'request_id': uuid4().hex, 'spec': spec, 'confirm_send': True}).json()
        encoded = ProductSetSpec(**spec).model_dump_json(exclude={'preset_id'})
        with closing(db.get_connection()) as con:
            actual = con.execute('SELECT payload_hash FROM product_sets WHERE batch_id=?', (result['batch_id'],)).fetchone()[0]
        self.assertEqual(actual, hashlib.sha256(encoded.encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
