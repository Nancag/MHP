"""Bilingual draft generation and private exports, with explicit consent and idempotency."""
import hashlib
import json
import threading
from contextlib import closing
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.auth import CurrentUser
from app.models import db
from app.services import copywriter
from app.services.library_service import now
from app.services.product_document import build_docx

router = APIRouter(prefix='/api/mkhp', tags=['MKHP 双语介绍'])
_workers = threading.BoundedSemaphore(2)


class DraftRequest(BaseModel):
    import_id: str = Field(pattern=r'^[0-9a-f]{32}$')
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    model: str = Field(min_length=1, max_length=120)
    language: str = Field(min_length=2, max_length=10)
    requirements: str = Field(default='', max_length=2000)
    confirm_send: bool = False


def public(row):
    value = dict(row)
    value['content'] = json.loads(value.pop('content_json'))
    value['usage'] = json.loads(value.pop('usage_json'))
    value.pop('user_id', None); value.pop('payload_hash', None)
    return value


def _owned(draft_id, user_id):
    with closing(db.get_connection()) as con:
        row = con.execute('''SELECT d.*,p.source_url FROM product_drafts d JOIN product_imports p
            ON p.import_id=d.import_id AND p.user_id=d.user_id WHERE d.draft_id=? AND d.user_id=?''',
                          (draft_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, '双语介绍不存在')
    return public(row)


def recover_drafts():
    with closing(db.get_connection()) as con, con:
        con.execute("UPDATE product_drafts SET status='failed',error=?,updated_at=? WHERE status='pending'",
                    ('服务重启导致结果未确认；上游可能已计费，请检查账单后再决定是否重新生成', now()))


@router.get('/ai-capabilities')
def capabilities(user: CurrentUser):
    return copywriter.capabilities()


@router.get('/drafts')
def list_drafts(user: CurrentUser, import_id: str = Query(pattern=r'^[0-9a-f]{32}$')):
    with closing(db.get_connection()) as con:
        rows = con.execute('''SELECT d.*,p.source_url FROM product_drafts d JOIN product_imports p
            ON p.import_id=d.import_id AND p.user_id=d.user_id WHERE d.user_id=? AND d.import_id=?
            ORDER BY d.created_at DESC LIMIT 50''', (user['user_id'],import_id)).fetchall()
    return {'items':[public(r) for r in rows]}


@router.get('/drafts/{draft_id}')
def get_draft(draft_id: str, user: CurrentUser):
    return _owned(draft_id,user['user_id'])


@router.post('/drafts')
def generate_draft(payload: DraftRequest, user: CurrentUser):
    if not payload.confirm_send:
        raise HTTPException(400, '请先确认将已识别商品字段、目标语言及创作要求发送给所选大模型；可能产生费用')
    cap = copywriter.capabilities()
    if payload.language not in copywriter.LANGUAGES:
        raise HTTPException(400, '请选择支持的介绍语言')
    if not cap['configured'] or payload.model not in cap['models']:
        raise HTTPException(503, '后端密钥或可选模型尚未配置；请先完成模型权限确认')
    digest = hashlib.sha256(payload.model_dump_json(exclude={'confirm_send','request_id'}).encode()).hexdigest()
    with closing(db.get_connection()) as con:
        source = con.execute('SELECT * FROM product_imports WHERE import_id=? AND user_id=?',
                             (payload.import_id,user['user_id'])).fetchone()
        if not source:
            raise HTTPException(404, '商品采集记录不存在')
        if source['status'] != 'completed':
            raise HTTPException(409, '请先完成商品网页识别')
        fields = json.loads(source['result_json']).get('fields',{})
    if not fields.get('name',{}).get('value'):
        raise HTTPException(400, '未识别商品名称，请先确认商品网页可读取')
    if not _workers.acquire(blocking=False):
        raise HTTPException(429, '当前文本任务繁忙，请稍后再试')
    did = uuid4().hex
    try:
        with closing(db.get_connection()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            existing = con.execute('SELECT draft_id,payload_hash FROM product_drafts WHERE user_id=? AND request_id=?',
                                   (user['user_id'],payload.request_id)).fetchone()
            if existing:
                if existing['payload_hash'] != digest:
                    raise HTTPException(409, '同一请求编号对应的内容不同，请刷新后重试')
                return _owned(existing['draft_id'],user['user_id'])
            if con.execute("SELECT 1 FROM product_drafts WHERE user_id=? AND status='pending'",(user['user_id'],)).fetchone():
                raise HTTPException(409, '你的上一条文本任务尚未完成，请勿重复生成')
            con.execute('''INSERT INTO product_drafts(draft_id,user_id,import_id,request_id,payload_hash,model,
                language,requirements,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (did,user['user_id'],payload.import_id,payload.request_id,digest,payload.model,payload.language,
                 payload.requirements,'pending',now(),now()))
        try:
            # Page evidence is data only. Never send cookies, key, image bytes, or local paths.
            facts = {k:{'value':str(v.get('value',''))[:1000], 'evidence':str(v.get('evidence',''))[:500]}
                     for k,v in fields.items() if isinstance(v,dict)}
            content,usage = copywriter.generate(facts,payload.language,payload.model,payload.requirements)
            with closing(db.get_connection()) as con, con:
                con.execute("UPDATE product_drafts SET status='completed',content_json=?,usage_json=?,updated_at=? WHERE draft_id=?",
                            (json.dumps(content,ensure_ascii=False),json.dumps(usage),now(),did))
        except copywriter.ProviderError as exc:
            with closing(db.get_connection()) as con, con:
                con.execute("UPDATE product_drafts SET status='failed',error=?,updated_at=? WHERE draft_id=?", (str(exc),now(),did))
        except Exception:
            with closing(db.get_connection()) as con, con:
                con.execute("UPDATE product_drafts SET status='failed',error=?,updated_at=? WHERE draft_id=?",
                            ('生成结果保存失败；上游可能已计费，请检查后再决定是否重试',now(),did))
        return _owned(did,user['user_id'])
    finally:
        _workers.release()


@router.get('/drafts/{draft_id}/export')
def export_draft(draft_id: str, user: CurrentUser, format: Literal['json','docx'] = Query()):
    draft = _owned(draft_id,user['user_id'])
    if draft['status'] != 'completed':
        raise HTTPException(409, '仅能导出已完成的双语介绍')
    with closing(db.get_connection()) as con:
        source = con.execute('SELECT result_json FROM product_imports WHERE import_id=? AND user_id=?',
                             (draft['import_id'],user['user_id'])).fetchone()
    evidence = json.loads(source['result_json'])
    headers={'Content-Disposition':f'attachment; filename="MHP-product-{draft_id}.{format}"', 'Cache-Control':'no-store'}
    if format == 'json':
        return Response(json.dumps({**draft,'product_evidence':evidence},ensure_ascii=False,indent=2).encode(),
                        media_type='application/json', headers=headers)
    return Response(build_docx(draft,evidence),
                    media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', headers=headers)
