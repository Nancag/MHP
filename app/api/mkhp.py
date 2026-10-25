"""Browser-extension product imports and preserved legacy collection history."""
import io
import hashlib
import json
import logging
import re
import threading
import time
from contextlib import closing
from uuid import uuid4
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,urlunsplit,urlencode

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from PIL import Image
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.api.auth import CurrentUser
from app.models import db
from app.repositories.asset_repo import create_asset
from app.services.library_service import folder_for_source, now
from app.services.public_web import fetch_public, normalize_url
from app.services.storage_service import save_product_image, UPLOAD_DIR, MAX_IMAGE_PIXELS

router = APIRouter(prefix='/api/mkhp', tags=['MKHP 商品采集'])
COLLECTOR_ROOT = Path(__file__).resolve().parents[2] / 'extensions/mhp-collector'
from app.services.cost_estimator import CostInput, estimate


@router.post('/cost-estimate')
def cost_estimate(payload: CostInput, user: CurrentUser):
    return estimate(payload)

logger = logging.getLogger(__name__)
_workers = threading.BoundedSemaphore(2)


class BrowserField(BaseModel):
    model_config=ConfigDict(extra='forbid')
    value:str=Field(min_length=1,max_length=2000)
    evidence:str=Field(default='页面采集，用户确认',max_length=300)
    source_url:str=Field(default='',max_length=4096)


class BrowserImport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:int=Field(default=1,ge=1,le=1)
    request_id:str=Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    source_url:str=Field(max_length=4096)
    fields:dict[str,BrowserField]
    image_urls:list[str]=Field(default_factory=list,max_length=20)
    warnings:list[str]=Field(default_factory=list,max_length=5)
    confirm_import:bool=False

    @model_validator(mode='after')
    def validate_capture(self):
        allowed={'name','description','price','price_max','currency','size','package_size','material','width','height','depth','weight'}
        if not self.fields or 'name' not in self.fields or set(self.fields)-allowed:
            raise ValueError('需提供商品标题，且只能导入指定商品字段')
        if any(len(w)>300 for w in self.warnings):raise ValueError('采集提示过长')
        source=normalize_url(self.source_url);parts=urlsplit(source)
        allowed_hosts={'item.taobao.com':'id','detail.tmall.com':'id','mobile.yangkeduo.com':'goods_id','mobile.pinduoduo.com':'goods_id'}
        key=allowed_hosts.get(parts.hostname)
        if not key or parts.scheme!='https' or not re.fullmatch(r'\d+',parse_qs(parts.query).get(key,[''])[0]):
            raise ValueError('暂只支持淘宝、天猫及拼多多商品详情网址')
        # Tracking links for the same product share one source folder.
        self.source_url=urlunsplit(('https',parts.hostname,parts.path,urlencode({key:parse_qs(parts.query)[key][0]}),''))
        for url in self.image_urls:
            image=urlsplit(normalize_url(url));host=image.hostname or ''
            if image.scheme!='https' or not any(host==d or host.endswith('.'+d) for d in ('alicdn.com','taobaocdn.com','pddpic.com','yangkeduo.com')):
                raise ValueError('候选图片须来自所支持平台的HTTPS图片域名')
        if len(set(self.image_urls))!=len(self.image_urls):raise ValueError('图片链接重复')
        return self


def browser_import_images(iid,user_id,source,result):
    try:
        folder=folder_for_source(user_id,source,result['fields']['name']['value'])
        update(iid,folder_id=folder['folder_id'])
        _download_images(iid,user_id,folder['folder_id'],result,result['image_urls'],time.monotonic()+90)
        update(iid,status='completed',result_json=json.dumps(result,ensure_ascii=False))
    except Exception:
        update(iid,status='failed',error='浏览器资料已接收，图片归档或本地保存失败；未自动重试',result_json=json.dumps(result,ensure_ascii=False))
    finally:_workers.release()


@router.post('/browser-imports',status_code=202)
def import_browser_capture(payload:BrowserImport,user:CurrentUser,background:BackgroundTasks):
    if not payload.confirm_import:raise HTTPException(400,'请先核对资料并确认下载所选图片')
    digest=hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    iid=hashlib.sha256((user['user_id']+':browser:'+payload.request_id).encode()).hexdigest()[:32]
    if not _workers.acquire(blocking=False):raise HTTPException(429,'采集任务繁忙，请稍后再试')
    try:
        with closing(db.get_connection()) as con,con:
            con.execute('BEGIN IMMEDIATE')
            existing=con.execute('SELECT * FROM product_imports WHERE import_id=? AND user_id=?',(iid,user['user_id'])).fetchone()
            if existing:
                if json.loads(existing['result_json']).get('browser_request_hash')!=digest:raise HTTPException(409,'同一请求编号不能导入不同资料')
                _workers.release();return {'import_id':iid,'status':existing['status']}
            if con.execute("SELECT 1 FROM product_imports WHERE user_id=? AND status='pending'",(user['user_id'],)).fetchone():raise HTTPException(409,'请等待现有采集任务完成')
            fields={k:{'value':v.value,'evidence':'浏览器采集（用户确认）：'+v.evidence,'source_url':payload.source_url} for k,v in payload.fields.items()}
            result={'fields':fields,'missing_fields':[k for k in ('name','price','size','package_size','material') if k not in fields],
                    'image_urls':payload.image_urls,'images':[],'image_errors':[],
                    'warnings':[*payload.warnings,'浏览器采集资料未经平台API核验；字段、价格和图片需人工核对。'],
                    'capture_method':'browser-extension','browser_request_hash':digest,'fetched_at':now(),'final_url':payload.source_url}
            con.execute('INSERT INTO product_imports VALUES (?,?,?,?,?,?,?,?,?)',(iid,user['user_id'],payload.source_url,None,'pending',json.dumps(result,ensure_ascii=False),None,now(),now()))
    except Exception:
        _workers.release();raise
    background.add_task(browser_import_images,iid,user['user_id'],payload.source_url,result)
    return {'import_id':iid,'status':'pending'}


@router.get('/collector/download')
def download_collector():
    import tempfile,zipfile
    from fastapi.responses import FileResponse
    from starlette.background import BackgroundTask
    root=COLLECTOR_ROOT
    names=('manifest.json','popup.html','popup.css','popup.js','extractor.js','bridge.js','background.js','README.md')
    if any(not (root/name).is_file() for name in names):raise HTTPException(503,'插件安装包尚未准备完整')
    with tempfile.NamedTemporaryFile(suffix='.zip',delete=False) as file:path=Path(file.name)
    try:
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
            for name in names:archive.write(root/name,arcname='mhp-collector/'+name)
    except Exception:
        path.unlink(missing_ok=True);raise
    version = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))['version']
    return FileResponse(path,filename=f'MHP-Collector-{version}.zip',media_type='application/zip',headers={'Cache-Control':'no-store'},background=BackgroundTask(path.unlink,missing_ok=True))


@router.get('/collector/installer')
def download_collector_installer():
    """Serve only a complete helper matching the current extension sources."""
    from fastapi.responses import FileResponse
    executable = COLLECTOR_ROOT / 'MHP-Collector-Setup.exe'
    try:
        build = json.loads((COLLECTOR_ROOT / 'installer-build.json').read_text(encoding='utf-8'))
        names = ('manifest.json', 'popup.html', 'popup.css', 'popup.js', 'extractor.js', 'bridge.js', 'background.js', 'README.md')
        if set(build['files']) != set(names) or executable.stat().st_size > 5 * 1024 * 1024:
            raise ValueError('invalid package')
        for name in names:
            if hashlib.sha256((COLLECTOR_ROOT / name).read_bytes()).hexdigest() != build['files'][name]:
                raise ValueError('stale package')
        if hashlib.sha256(executable.read_bytes()).hexdigest() != build['exe_sha256']:
            raise ValueError('invalid helper')
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Windows 安装辅助工具尚未构建或与当前插件不一致，请使用插件 ZIP 或联系管理员') from None
    return FileResponse(executable, filename='MHP-Collector-Setup.exe', media_type='application/octet-stream',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


class ImportURL(BaseModel):
    url: str = Field(min_length=8, max_length=4096)
    confirm_fetch: bool = False


class ImageBatch(BaseModel):
    confirm_fetch: bool = False
    retry_failed: bool = False


def public(row):
    value = dict(row)
    value['result'] = json.loads(value.pop('result_json'))
    value.pop('user_id', None)
    images = value['result'].get('images', [])
    attempted = {i['source_url'] for i in images} | {i['source_url'] for i in value['result'].get('image_errors',[])}
    value['result']['remaining_images'] = len([u for u in value['result'].get('image_urls',[]) if u not in attempted])
    if images:
        with closing(db.get_connection()) as con:
            active = {r[0] for r in con.execute('SELECT asset_id FROM assets WHERE user_id=? AND deleted_at IS NULL', (row['user_id'],))}
        visible = [i for i in images if i['asset_id'] in active]
        value['result']['removed_image_count'] = len(images) - len(visible)
        value['result']['images'] = visible
    return value


def more_images(import_id, user_id, folder_id, result, urls):
    try:
        result['image_errors'] = [e for e in result.get('image_errors',[]) if e['source_url'] not in urls]
        _download_images(import_id,user_id,folder_id,result,urls,time.monotonic()+90)
        update(import_id,status='completed',error=None,result_json=json.dumps(result,ensure_ascii=False))
    except Exception:
        update(import_id,status='failed',error='追加图片采集或保存失败；已保存素材保留',result_json=json.dumps(result,ensure_ascii=False))
    finally:
        _workers.release()


@router.post('/imports/{import_id}/images',status_code=202)
def import_image_batch(import_id: str, user: CurrentUser, payload: ImageBatch, background: BackgroundTasks):
    if not payload.confirm_fetch:
        raise HTTPException(400,'请先确认继续访问图片来源并保存图片')
    if not _workers.acquire(blocking=False):
        raise HTTPException(429,'图片采集繁忙，请稍后再试')
    try:
        with closing(db.get_connection()) as con,con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM product_imports WHERE import_id=? AND user_id=?',(import_id,user['user_id'])).fetchone()
            if not row:
                raise HTTPException(404,'商品采集记录不存在')
            if con.execute("SELECT 1 FROM product_imports WHERE user_id=? AND status='pending'",(user['user_id'],)).fetchone():
                raise HTTPException(409,'请等待现有采集任务完成')
            if not row['folder_id']:
                raise HTTPException(409,'当前记录尚未创建图片归档文件夹，请重新采集')
            result=json.loads(row['result_json'])
            attempted={i['source_url'] for i in result.get('images',[])} | {i['source_url'] for i in result.get('image_errors',[])}
            urls=([i['source_url'] for i in result.get('image_errors',[])] if payload.retry_failed else
                  [u for u in result.get('image_urls',[]) if u not in attempted])[:20]
            if not urls:
                raise HTTPException(409,'没有待采集的图片')
            con.execute("UPDATE product_imports SET status='pending',error=NULL,updated_at=? WHERE import_id=?",(now(),import_id))
    except Exception:
        _workers.release()
        raise
    background.add_task(more_images,import_id,user['user_id'],row['folder_id'],result,urls)
    return {'import_id':import_id,'status':'pending','batch_count':len(urls)}


def recover_imports():
    """Called once on application startup, never replay downloads automatically."""
    with closing(db.get_connection()) as con, con:
        con.execute("UPDATE product_imports SET status='failed',error=?,updated_at=? WHERE status='pending'",
                    ('采集因服务重启而中断；已保存的素材保留，请手动重新采集', now()))


def update(import_id, **values):
    values['updated_at'] = now()
    with closing(db.get_connection()) as con, con:
        con.execute('UPDATE product_imports SET ' + ','.join(k+'=?' for k in values) + ' WHERE import_id=?',
                    [*values.values(), import_id])


def _download_images(import_id, user_id, folder_id, result, urls, deadline):
    remaining = 60 * 1024 * 1024
    for image_url in urls:
        saved = None
        try:
            if time.monotonic() >= deadline or remaining <= 0:
                raise ValueError('本次采集时长或总图片下载量已达上限')
            image_bytes, kind, _ = fetch_public(image_url, limit=min(10*1024*1024, remaining), deadline=deadline)
            remaining -= len(image_bytes)
            with Image.open(io.BytesIO(image_bytes)) as image:
                if image.width*image.height > MAX_IMAGE_PIXELS or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('图片尺寸或动画格式不受支持')
                if image.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError('只采集 JPG、PNG、WebP 图片')
                image.load()
                if image.format == 'WEBP':
                    converted = io.BytesIO()
                    image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(converted, format='PNG')
                    image_bytes = converted.getvalue()
            saved = save_product_image(image_bytes, folder_id=folder_id)
            asset = create_asset({**saved, 'user_id': user_id, 'role': 'reference',
                                  'folder_id': folder_id, 'source_url': image_url})
            result['images'].append({'asset_id': asset['asset_id'], 'source_url': image_url,
                                     'preview_url': f"/api/assets/{asset['asset_id']}/preview"})
        except Exception as exc:
            if saved:
                (UPLOAD_DIR / saved['filename']).unlink(missing_ok=True)
            message = str(exc) if isinstance(exc, ValueError) else '图片下载或保存失败'
            result['image_errors'].append({'source_url': image_url, 'message': message[:300]})
        update(import_id, result_json=json.dumps(result, ensure_ascii=False))


@router.post('/imports', status_code=202)
def start_import(user: CurrentUser, payload: ImportURL, background: BackgroundTasks):
    raise HTTPException(410, '静态网页采集已停用。请在 Edge 商品页使用 MHP 商品采集助手；已有采集历史和图片保留。')


@router.get('/imports')
def list_imports(user: CurrentUser, page: int = Query(1, ge=1)):
    with closing(db.get_connection()) as con:
        rows = con.execute('SELECT * FROM product_imports WHERE user_id=? ORDER BY created_at DESC LIMIT 30 OFFSET ?',
                           (user['user_id'], (page-1)*30)).fetchall()
    return {'items': [public(r) for r in rows]}


@router.get('/imports/{import_id}')
def get_import(import_id: str, user: CurrentUser):
    with closing(db.get_connection()) as con:
        row = con.execute('SELECT * FROM product_imports WHERE import_id=? AND user_id=?', (import_id, user['user_id'])).fetchone()
    if not row:
        raise HTTPException(404, '采集记录不存在')
    return public(row)
