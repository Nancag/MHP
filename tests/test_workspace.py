import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
from contextlib import ExitStack,closing
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from PIL import Image
from app.api import workspace as routes,assets,auth
from app.models import db
from app.repositories.asset_repo import create_asset
from support_client import Client


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        self.root=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(db,'DB_PATH',self.root/'test.db'))
        stack.enter_context(patch.object(assets,'UPLOAD_DIR',self.root/'uploads'))
        stack.enter_context(patch.dict(os.environ,{'MHP_ADMIN_EMAILS':'admin@example.com','MHP_OPERATIONS_DIR':str(self.root/'operations')}))
        db.init_db();self.user={'user_id':'owner','email':'owner@example.com'}
        app=FastAPI();app.include_router(routes.router);app.include_router(assets.router)
        app.dependency_overrides[auth.require_user]=lambda:self.user
        self.client=Client(app)

    def test_preferences_are_persistent_and_owned(self):
        status,value=self.client.call('PUT','/api/workspace/settings',{'theme':'light','resolution':'1200'})
        self.assertEqual(status,200,value)
        self.assertEqual(self.client.call('GET','/api/workspace/settings')[1]['preferences']['theme'],'light')
        self.user['user_id']='other'
        self.assertEqual(self.client.call('GET','/api/workspace/settings')[1]['preferences']['theme'],'dark')
        self.assertEqual(self.client.call('PUT','/api/workspace/settings',{'resolution':'4000'})[0],422)

    def test_template_crud_search_and_asset_sanitization(self):
        value={'name':'  Minimal  ','description':'blue','payload':{'params':{'resolution':'1200'},'spec':{'resolution':'1200','reference_ids':['private'],'pages':[{'asset_id':'private','cutout_id':'private'}]}}}
        status,item=self.client.call('POST','/api/workspace/templates',value);self.assertEqual(status,201,item)
        item=routes.templates(self.user,'BLUE')['items'][0]
        self.assertEqual(item['payload']['spec']['reference_ids'],[])
        self.assertEqual(item['payload']['spec']['pages'][0]['asset_id'],'')
        self.user['user_id']='other';self.assertEqual(routes.templates(self.user,'')['items'],[])
        self.assertEqual(self.client.call('DELETE','/api/workspace/templates/'+item['template_id'])[0],404)
        self.user['user_id']='owner';self.assertEqual(self.client.call('DELETE','/api/workspace/templates/'+item['template_id'])[0],200)
        self.assertEqual(self.client.call('POST','/api/workspace/templates',{'name':'bad','payload':{'params':{'resolution':'4000'}}})[0],422)

    def test_research_statistics_sources_export_and_ownership(self):
        data={'title':'Test','currency':'USD','own_price':30,'competitors':[{'name':'=FORMULA','url':'https://example.com/a','collected_on':'2026-10-18','price':10},{'name':'B','url':'https://example.com/b','collected_on':'2026-10-18','price':30}]}
        status,value=self.client.call('POST','/api/workspace/research',data);self.assertEqual(status,201,value)
        self.assertEqual(value['statistics']['median'],20);self.assertEqual(value['statistics']['own_vs_median_percent'],50)
        exported=routes.export_research(value['project_id'],self.user).body.decode('utf-8-sig');self.assertIn("'=FORMULA",exported)
        self.user['user_id']='other';self.assertEqual(self.client.call('GET','/api/workspace/research')[1]['items'],[])
        self.assertEqual(self.client.call('PUT','/api/workspace/research/'+value['project_id'],data)[0],404)
        data['competitors'][0]['url']='javascript:alert(1)';self.assertEqual(self.client.call('POST','/api/workspace/research',data)[0],422)

    def asset(self):
        aid='a'*32;folder=self.root/'uploads';folder.mkdir(exist_ok=True)
        Image.new('RGB',(10,10),'red').save(folder/(aid+'.png'))
        create_asset(dict(asset_id=aid,filename=aid+'.png',user_id='owner',role='product',width=10,height=10,format='PNG',size_bytes=100))
        return aid

    def test_image_delete_moves_file_hides_list_and_restores(self):
        aid=self.asset()
        self.assertEqual(self.client.call('DELETE','/api/assets/'+aid)[0],200)
        self.assertFalse((self.root/'uploads'/(aid+'.png')).exists());self.assertTrue((self.root/'trash'/(aid+'.png')).exists())
        self.assertEqual(self.client.call('GET','/api/assets')[1]['total'],0)
        self.assertEqual(self.client.call('GET',f'/api/assets/{aid}/preview')[0],404)
        self.assertEqual(self.client.call('GET','/api/assets/trash')[1]['items'][0]['asset_id'],aid)
        self.assertEqual(self.client.call('POST',f'/api/assets/{aid}/restore',{})[0],200)
        self.assertTrue((self.root/'uploads'/(aid+'.png')).exists());self.assertEqual(self.client.call('GET','/api/assets')[1]['total'],1)

    def test_other_user_cannot_delete_or_restore(self):
        aid=self.asset();self.user['user_id']='other'
        self.assertEqual(self.client.call('DELETE','/api/assets/'+aid)[0],404)
        self.assertTrue((self.root/'uploads'/(aid+'.png')).exists())

    def test_active_generation_prevents_deletion(self):
        aid=self.asset()
        with closing(db.get_connection()) as con,con:
            con.execute("INSERT INTO generations(generation_id,asset_id,user,prompt,model,size,status,created_at) VALUES ('busy',?,'owner','test','test','1200','pending','now')",(aid,))
        self.assertEqual(self.client.call('DELETE','/api/assets/'+aid)[0],409)
        self.assertTrue((self.root/'uploads'/(aid+'.png')).exists())

    def test_expired_trash_is_permanently_purged(self):
        aid=self.asset()
        result=self.client.call('DELETE','/api/assets/'+aid)[1]
        self.assertEqual(result['retention_days'],30)
        with closing(db.get_connection()) as con,con:
            con.execute('UPDATE assets SET deleted_at=? WHERE asset_id=?',(int(time.time())-31*86400,aid))
        with patch.dict(os.environ,{'MHP_TRASH_RETENTION_DAYS':'30'}):
            self.assertEqual(assets.purge_expired_trash(),1)
        self.assertFalse((self.root/'trash'/(aid+'.png')).exists())
        with closing(db.get_connection()) as con:
            self.assertIsNone(con.execute('SELECT 1 FROM assets WHERE asset_id=?',(aid,)).fetchone())

    def test_backup_admin_confirmation_and_queue(self):
        self.assertEqual(self.client.call('GET','/api/workspace/backups')[0],403)
        self.user['email']='admin@example.com'
        self.assertEqual(self.client.call('POST','/api/workspace/backups',{'action':'backup'})[0],503)
        root=routes.operations_root();root.mkdir();(root/'heartbeat').touch();(root/'index.json').write_text(json.dumps([{'backup_id':'known'}]))
        self.assertEqual(self.client.call('POST','/api/workspace/backups',{'action':'restore','backup_id':'known'})[0],400)
        self.assertEqual(self.client.call('POST','/api/workspace/backups',{'action':'restore','backup_id':'../secret','confirmation':'恢复整站'})[0],422)
        status,value=self.client.call('POST','/api/workspace/backups',{'action':'backup'});self.assertEqual(status,202,value)
        self.assertEqual(self.client.call('POST','/api/workspace/backups',{'action':'backup'})[0],409)


class BackupRecoveryTests(unittest.TestCase):
    def test_real_archive_restore_in_isolated_directory_preserves_models_and_expires_sessions(self):
        # Only Docker orchestration is mocked. Archive, checksum, database and files are real.
        source=Path(__file__).resolve().parents[1]/'deploy/backup_worker.py'
        spec=importlib.util.spec_from_file_location('isolated_backup_worker',source);worker=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'fcntl':types.SimpleNamespace()}):spec.loader.exec_module(worker)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);worker.SITE=root/'site';worker.SITE.mkdir();worker.STORE=root/'backups';worker.STORE.mkdir();worker.OPS=root/'ops';worker.OPS.mkdir()
            for name in ('app/models','frontend/dist','deploy','data/models'):(worker.SITE/name).mkdir(parents=True,exist_ok=True)
            (worker.SITE/'app/models/db.py').write_text('original code');(worker.SITE/'data/models/model.onnx').write_text('keep model')
            (worker.SITE/'data/picture.png').write_text('original image')
            env='PRIVATE=not-for-output\n# Keep other settings\nMHP_TEXT_MODELS=claude-sonnet-4-6\nMHP_TEXT_API_KEY=offline-text-token\nMHP_IMAGE_API_KEY=offline-image-token\n'
            (worker.SITE/'.env').write_text(env)
            with sqlite3_connection(worker.SITE/'data/mhp.db') as con:
                con.execute('CREATE TABLE auth_sessions(token TEXT)');con.execute("INSERT INTO auth_sessions VALUES ('old-session')");con.execute('CREATE TABLE auth_codes(code TEXT)')
            with patch.object(worker,'run',return_value='sha256:fixture'),patch.object(worker,'ready'),patch.object(worker.os,'chown',create=True):
                bid=worker.backup()
                import tarfile
                with tarfile.open(worker.STORE/(bid+'.tar.gz')) as archive:
                    saved=archive.extractfile('.env').read().decode()
                    self.assertIn('PRIVATE=not-for-output',saved)
                    self.assertIn('MHP_TEXT_MODELS=claude-sonnet-4-6',saved)
                    for forbidden in ('MHP_TEXT_API_KEY','MHP_IMAGE_API_KEY','offline-text-token','offline-image-token'):
                        self.assertNotIn(forbidden,saved)
                self.assertEqual((worker.SITE/'.env').read_text(),env)
                (worker.SITE/'data/picture.png').write_text('changed image')
                worker.restore(bid,safety=False)
            self.assertEqual((worker.SITE/'.env').read_bytes(),saved.encode())
            self.assertEqual((worker.SITE/'app/models/db.py').read_text(),'original code')
            self.assertEqual((worker.SITE/'data/picture.png').read_text(),'original image')
            self.assertEqual((worker.SITE/'data/models/model.onnx').read_text(),'keep model')
            with sqlite3_connection(worker.SITE/'data/mhp.db') as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM auth_sessions').fetchone()[0],0)
            (worker.STORE/(bid+'.tar.gz')).write_bytes(b'tampered')
            with self.assertRaises(ValueError):worker.restore(bid,safety=False)

    def test_backup_env_filter_removes_duplicate_export_and_bom_assignments(self):
        source=Path(__file__).resolve().parents[1]/'deploy/backup_worker.py'
        spec=importlib.util.spec_from_file_location('isolated_env_filter',source);worker=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'fcntl':types.SimpleNamespace()}):spec.loader.exec_module(worker)
        content=b'\xef\xbb\xbfMHP_TEXT_API_KEY="offline-1"\r\n export MHP_IMAGE_API_KEY = offline-2\r\nMHP_TEXT_API_KEY=offline-3\r\nOTHER=keep\r\n# comment\r\nMHP_TEXT_MODELS=claude-sonnet-4-6\r\n'
        clean=worker.sanitized_env(content)
        self.assertEqual(clean,b'OTHER=keep\r\n# comment\r\nMHP_TEXT_MODELS=claude-sonnet-4-6\r\n')

def sqlite3_connection(path):
    import sqlite3
    from contextlib import contextmanager
    @contextmanager
    def opened():
        with closing(sqlite3.connect(path)) as con,con:yield con
    return opened()
