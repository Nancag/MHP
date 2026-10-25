"""Private, consented multimodal planning jobs with durable idempotency."""
import hashlib
import json
import threading
from contextlib import closing
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.api.auth import CurrentUser
from app.models import db
from app.repositories.ownership import owned_record
from app.services import product_planner, storage_service
from app.services import official_templates
from app.services.library_service import now

router = APIRouter(prefix='/api/product-plans', tags=['PTMD 双语套图策划'])
_workers = threading.BoundedSemaphore(2)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    model: str = Field(min_length=1, max_length=120)
    language: str = Field(pattern=r'^(ru|en|de|fr|es|pt)$')
    count: int = Field(ge=1, le=9, strict=True)
    image_ids: list[str] = Field(min_length=1, max_length=9)
    import_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{32}$')
    confirmed_facts: str = Field(default='', max_length=4000)
    wishes: str = Field(min_length=1, max_length=4000)
    confirm_facts: bool = False
    confirm_send: bool = False
    preset_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode='after')
    def check_preset(self):
        official_templates.check_selection(self.preset_id, self.count, self.language)
        return self

    @field_validator('image_ids')
    @classmethod
    def check_ids(cls, values):
        import re
        if len(set(values)) != len(values) or any(not re.fullmatch(r'[0-9a-f]{32}', s) for s in values):
            raise ValueError('商品图片编号无效或重复')
        return values


def _public(row):
    value = dict(row)
    value['request'] = json.loads(value.pop('request_json'))
    value['content'] = json.loads(value.pop('content_json'))
    value['usage'] = json.loads(value.pop('usage_json'))
    for key in ('user_id', 'payload_hash', 'submitted'):
        value.pop(key, None)
    return value


def _owned(plan_id, user_id):
    with closing(db.get_connection()) as con:
        row = con.execute('SELECT * FROM product_plans WHERE plan_id=? AND user_id=?', (plan_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, '套图策划不存在')
    return _public(row)


def recover_plans():
    with closing(db.get_connection()) as con, con:
        con.execute("UPDATE product_plans SET status='failed',error=?,updated_at=? WHERE status='pending'",
                    ('服务重启，策划结果未确认；上游可能已计费，请核对账单后再决定是否重新生成', now()))


def _images(ids, user_id):
    images = {}
    for aid in ids:
        asset = owned_record('asset', aid, user_id)
        path = (storage_service.UPLOAD_DIR / asset['filename']).resolve()
        if not path.is_relative_to(storage_service.UPLOAD_DIR.resolve()) or not path.is_file():
            raise HTTPException(404, '选定商品图片已不存在')
        images[aid] = path
    return images


def _fields(payload, user_id):
    fields = {}
    if payload.import_id:
        with closing(db.get_connection()) as con:
            row = con.execute('SELECT * FROM product_imports WHERE import_id=? AND user_id=?',
                              (payload.import_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, '商品采集记录不存在')
        if row['status'] != 'completed':
            raise HTTPException(409, '商品采集尚未完成')
        raw = json.loads(row['result_json']).get('fields', {})
        fields = {k: str(v.get('value', '')).strip()[:1000] for k, v in raw.items()
                  if isinstance(v, dict) and str(v.get('value', '')).strip()}
    if payload.confirmed_facts:
        fields['seller_facts'] = payload.confirmed_facts
    return fields


@router.get('/capabilities')
def capabilities(user: CurrentUser):
    return product_planner.capabilities()


@router.get('')
def list_plans(user: CurrentUser):
    with closing(db.get_connection()) as con:
        rows = con.execute('SELECT * FROM product_plans WHERE user_id=? ORDER BY created_at DESC LIMIT 30',
                           (user['user_id'],)).fetchall()
    return {'items': [_public(row) for row in rows]}


@router.get('/{plan_id}')
def get_plan(plan_id: str, user: CurrentUser):
    return _owned(plan_id, user['user_id'])


@router.post('', status_code=202)
def create_plan(payload: PlanRequest, user: CurrentUser):
    if not payload.confirm_send or not payload.confirm_facts:
        raise HTTPException(400, '请先核对商品事实，并确认向文案服务发送选定图片、字段与需求；可能产生费用')
    excluded = {'request_id', 'confirm_send', 'confirm_facts'}
    if payload.preset_id is None:
        excluded.add('preset_id')  # Preserve hashes of requests created before official templates.
    digest = hashlib.sha256(payload.model_dump_json(exclude=excluded).encode()).hexdigest()
    with closing(db.get_connection()) as con:
        existing = con.execute('SELECT * FROM product_plans WHERE user_id=? AND request_id=?',
                               (user['user_id'], payload.request_id)).fetchone()
    if existing:
        if existing['payload_hash'] != digest:
            raise HTTPException(409, '同一请求编号不能用于不同策划要求')
        return _public(existing)
    cap = product_planner.capabilities()
    if not cap['configured'] or payload.model not in cap['models']:
        raise HTTPException(503, '请先配置后端文案服务并选择可用模型')
    _images(payload.image_ids, user['user_id'])
    fields = _fields(payload, user['user_id'])
    if not fields:
        raise HTTPException(400, '请提供已确认商品名称与事实；风格需求请填写在大白话需求中')
    request = payload.model_dump(exclude={'request_id', 'confirm_send', 'confirm_facts'})
    request['facts'] = fields
    if not _workers.acquire(blocking=False):
        raise HTTPException(429, '文案策划任务繁忙，请稍后再试')
    plan_id = uuid4().hex
    handed_off = False
    try:
        with closing(db.get_connection()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            existing = con.execute('SELECT * FROM product_plans WHERE user_id=? AND request_id=?',
                                   (user['user_id'], payload.request_id)).fetchone()
            if existing:
                if existing['payload_hash'] != digest:
                    raise HTTPException(409, '同一请求编号不能用于不同策划要求')
                return _public(existing)
            if con.execute("SELECT 1 FROM product_plans WHERE user_id=? AND status='pending'", (user['user_id'],)).fetchone():
                raise HTTPException(409, '上一条策划尚未结束，请勿重复提交')
            con.execute('''INSERT INTO product_plans
                (plan_id,user_id,request_id,payload_hash,request_json,status,created_at,updated_at)
                VALUES (?,?,?,?,?,'pending',?,?)''',
                        (plan_id, user['user_id'], payload.request_id, digest,
                         json.dumps(request, ensure_ascii=False), now(), now()))
        try:
            threading.Thread(target=_run, args=(plan_id, user['user_id']), daemon=True).start()
            handed_off = True
        except Exception:
            _fail(plan_id, '策划任务未能启动，未自动重试')
        return _owned(plan_id, user['user_id'])
    finally:
        if not handed_off:
            _workers.release()


class PlanEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content: product_planner.PlanContent
    confirm_save: bool = False


@router.put('/{plan_id}')
def save_plan(plan_id: str, payload: PlanEdit, user: CurrentUser):
    if not payload.confirm_save:
        raise HTTPException(400, '请先确认保存并应用已核实的文案；此操作不调用模型')
    job = _owned(plan_id, user['user_id'])
    if job['status'] != 'completed':
        raise HTTPException(409, '仅能编辑已完成的策划')
    request = job['request']
    try:
        content = product_planner.validate_content(payload.content.model_dump(), request['facts'], request['language'],
                                                   request['image_ids'], request['count'], request.get('preset_id'))
    except ValueError:
        raise HTTPException(400, '请检查页数、文案语言、商品素材和事实引用；专用模板尺寸仅限主图') from None
    _images(request['image_ids'], user['user_id'])
    with closing(db.get_connection()) as con, con:
        con.execute('UPDATE product_plans SET content_json=?,updated_at=? WHERE plan_id=? AND user_id=?',
                    (json.dumps(content, ensure_ascii=False), now(), plan_id, user['user_id']))
    return _owned(plan_id, user['user_id'])


def _fail(plan_id, message):
    with closing(db.get_connection()) as con, con:
        con.execute("UPDATE product_plans SET status='failed',error=?,updated_at=? WHERE plan_id=? AND status='pending'",
                    (message, now(), plan_id))


def _run(plan_id, user_id):
    try:
        with closing(db.get_connection()) as con, con:
            claim = con.execute("UPDATE product_plans SET submitted=1 WHERE plan_id=? AND user_id=? AND status='pending' AND submitted=0",
                                (plan_id, user_id))
            if not claim.rowcount:
                return
        job = _owned(plan_id, user_id)['request']
        images = _images(job['image_ids'], user_id)
        options = {'preset_id': job['preset_id']} if job.get('preset_id') else {}
        content, usage = product_planner.generate(job['facts'], job['language'], job['model'], job['wishes'], images, job['count'], **options)
        # Validate again even if a future adapter returns an unexpected object.
        content = product_planner.validate_content(content, job['facts'], job['language'], images, job['count'], job.get('preset_id'))
        with closing(db.get_connection()) as con, con:
            con.execute("UPDATE product_plans SET status='completed',content_json=?,usage_json=?,updated_at=? WHERE plan_id=? AND status='pending'",
                        (json.dumps(content, ensure_ascii=False), json.dumps(usage), now(), plan_id))
    except product_planner.ProviderError as exc:
        _fail(plan_id, str(exc))
    except Exception:
        _fail(plan_id, '策划处理或保存失败；如已提交上游则可能计费，未自动重试')
    finally:
        _workers.release()
