"""Atomic credit reservations and sequential reference-image ecommerce jobs."""
import hashlib
import io
import json
import logging
import threading
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from app.api.auth import CurrentUser
from app.api.generations import _preview, _safe_update
from app.models import db
from app.repositories.ownership import owned_record
from app.services import reference_service as provider
from app.services import storage_service, generation_service
from app.services.credit_service import reserve_credit, settle
from app.services.product_set_service import ProductSetSpec, validate_copy, output_size, build_instruction, render_copy, render_material, material_image

router=APIRouter(prefix='/api/product-sets',tags=['电商套图'])
logger=logging.getLogger(__name__)
export_lock=threading.BoundedSemaphore(1)
material_lock=threading.BoundedSemaphore(1)
LOCAL_MODEL='local-material-layout-v1'


def _local(spec):return spec.engine=='local'


def _validate(spec,user_id):
    try:
        if spec.engine == 'reference' and not spec.text_rendering:
            raise ValueError('请先选择程序精确排字或模型直接生成图文')
        if spec.engine == 'local' and spec.text_rendering == 'model':
            raise ValueError('模型图文排版需要选择 GPT Image 2 制作方式')
        validate_copy(spec)
        if not _local(spec):
            for i in range(spec.count):
                if len(build_instruction(spec,i))>8000:
                    raise ValueError('创作要求过长，请精简，避免模型截断')
    except (ValueError,OSError) as exc:
        raise HTTPException(400,'字体或文案不可用，请检查' if isinstance(exc,OSError) else str(exc)) from exc
    paths=_assets(spec,user_id)
    if _local(spec):
        for page in spec.pages:
            try:material_image(paths[page.asset_id],page)
            except Exception:raise HTTPException(400,'商品素材或裁切区域不可用，请重新选择')
    return paths


def _brief(spec,index):
    if not _local(spec):return build_instruction(spec,index)
    return json.dumps({'engine':'local','page':spec.pages[index].model_dump(),'palette':spec.palette,
                       'requirements':spec.requirements,'note':'本地仅执行素材、裁切、配色和文案设置，不生成新场景或视角'},ensure_ascii=False)


def _upscaled(item,long_edge):
    workflow=item.get('workflow') or {}
    if workflow.get('engine')=='local':
        region=workflow.get('material_region_size') or []
        placed=workflow.get('placed_size') or []
        return long_edge>max(item['width'],item['height']) or any(p>r for p,r in zip(placed,region))
    native=max(workflow.get('native_width') or 2048,workflow.get('native_height') or 2048)
    return long_edge>min(native,max(item['width'],item['height']))


class SetRequest(BaseModel):
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    spec: ProductSetSpec
    confirm_send: bool = False


def _id(value):
    import re
    if not re.fullmatch(r'[0-9a-f]{32}',value):raise HTTPException(400,'任务编号格式不正确')


def _batch(batch_id,user_id):
    _id(batch_id)
    from app.repositories.recovery import reconcile
    reconcile()
    with closing(db.get_connection()) as con:
        batch=con.execute('SELECT * FROM product_sets WHERE batch_id=? AND user_id=?',(batch_id,user_id)).fetchone()
        if not batch:raise HTTPException(404,'套图任务不存在')
        rows=con.execute('SELECT * FROM generations WHERE batch_id=? AND user=? AND page_index>=0 ORDER BY page_index',(batch_id,user_id)).fetchall()
    items=[_preview(dict(row)) for row in rows]
    statuses=[row['status'] for row in items]
    status=('pending' if 'pending' in statuses else 'completed' if statuses and all(s=='completed' for s in statuses)
            else 'failed' if 'failed' in statuses else 'cancelled')
    return {'batch_id':batch_id,'spec':json.loads(batch['spec_json']),'created_at':batch['created_at'],
            'status':status,'items':items,'completed':statuses.count('completed'),
            'accepted':sum(row.get('review_status')=='accepted' for row in items),'count':len(items)}


def _assets(spec,user_id):
    paths={}
    for aid in {*[page.asset_id for page in spec.pages],*spec.reference_ids}:
        record=owned_record('asset',aid,user_id)
        path=storage_service.UPLOAD_DIR/record['filename']
        if not path.is_file():raise HTTPException(404,'商品图或示例图已不存在，请重新上传')
        try:
            from PIL import Image
            with Image.open(path) as image:image.verify()
        except Exception:raise HTTPException(400,'商品图或示例图已损坏，请重新上传')
        paths[aid]=path
    if any(page.asset_id in spec.reference_ids for page in spec.pages):
        raise HTTPException(400,'商品图与风格示例图请分别选择，避免混淆商品身份')
    return paths


@router.get('/capabilities')
def capabilities(user: CurrentUser):
    return {'local_layout':True,'reference_editing':provider.available(),'model':provider.MODEL,'max_count':9,'max_references':2,
            'text_rendering':['local','model'],
            'languages':['ru','en'],'export_long_edges':[1200,2000],
            'native_size':[1536,2048],'live_verified':False,'free_quota_enforced_by_provider':False,
            'note':'完整图文套图流程尚未完成渠道实测。AI 会发送商品原图、最多2张参考图与创作要求，上游另计费；每张另占1个MHP额度。支持1200/2000导出。'}


@router.post('',status_code=201)
def create_set(user: CurrentUser,payload: SetRequest):
    spec=payload.spec
    encoded=spec.model_dump_json()
    digest=hashlib.sha256(encoded.encode()).hexdigest()
    with closing(db.get_connection()) as con:
        existing=con.execute('SELECT batch_id,payload_hash FROM product_sets WHERE user_id=? AND request_id=?',
                             (user['user_id'],payload.request_id)).fetchone()
    if existing:
        if existing['payload_hash']!=digest:raise HTTPException(409,'同一请求编号不能用于不同套图要求')
        return _batch(existing['batch_id'],user['user_id'])
    if not _local(spec):
        if not payload.confirm_send:raise HTTPException(400,'请确认将商品图、参考图和创作要求发送至 AI 服务')
        if not spec.image_quality:raise HTTPException(400,'请自行选择图像质量后生成')
        if not provider.available():raise HTTPException(503,provider.NOT_CONFIGURED)
    _validate(spec,user['user_id'])
    batch_id=uuid4().hex
    stamp=datetime.now(timezone.utc).isoformat()
    try:
        with closing(db.get_connection()) as con,con:
            con.execute('BEGIN IMMEDIATE')
            # The unique request key is in the same transaction as all image/credit rows.
            existing=con.execute('SELECT batch_id,payload_hash FROM product_sets WHERE user_id=? AND request_id=?',
                                 (user['user_id'],payload.request_id)).fetchone()
            if existing:
                if existing['payload_hash']!=digest:raise HTTPException(409,'同一请求编号不能用于不同套图要求')
                batch_id=existing['batch_id']
            else:
                con.execute('INSERT INTO product_sets VALUES (?,?,?,?,?,?)',(batch_id,user['user_id'],payload.request_id,digest,encoded,stamp))
                width,height=output_size(spec)
                for i,page in enumerate(spec.pages):
                    gid=uuid4().hex
                    reserve_credit(con,user['user_id'],gid)
                    con.execute('''INSERT INTO generations
                        (generation_id,user,asset_id,prompt,full_prompt,model,size,quality,status,created_at,
                         ratio,resolution,language,type,workflow_json,batch_id,page_index,review_status)
                         VALUES (?,?,?,?,?,?,?,'standard','pending',?,'3:4',?,?,?, ?,?,?,'needs_review')''',
                        (gid,user['user_id'],page.asset_id,spec.requirements,_brief(spec,i),LOCAL_MODEL if _local(spec) else provider.MODEL,
                         f'{width}x{height}',stamp,spec.resolution,spec.language,'local_set' if _local(spec) else 'reference_set',
                         json.dumps({'engine':spec.engine,'text_rendering':spec.text_rendering,'page':page.model_dump(),'reference_ids':spec.reference_ids},ensure_ascii=False),batch_id,i))
    except HTTPException:raise
    except Exception:
        logger.exception('套图创建失败')
        raise HTTPException(503,'套图任务保存失败，请稍后重试')
    if not existing:
        threading.Thread(target=_run_set,args=(batch_id,user['user_id']),daemon=True).start()
    return _batch(batch_id,user['user_id'])


def _run_set(batch_id,user_id):
    state=_batch(batch_id,user_id)
    spec=ProductSetSpec.model_validate(state['spec'])
    for item in state['items']:
        gid=item['generation_id']
        raw=generation_service.GENERATION_DIR/f'.{gid}-reference.png'
        output=generation_service.GENERATION_DIR/f'{gid}.png'
        try:
            # Claim once. A second worker or repeated HTTP request cannot call the provider again.
            with closing(db.get_connection()) as con,con:
                con.execute('BEGIN IMMEDIATE')
                result=con.execute("UPDATE generations SET task_id=? WHERE generation_id=? AND status='pending' AND task_id IS NULL",(('local-' if _local(spec) else 'reference-')+uuid4().hex,gid))
                if not result.rowcount:continue
                if not _local(spec):con.execute("UPDATE credit_holds SET submitted=1 WHERE generation_id=? AND state='reserved'",(gid,))
            paths=_assets(spec,user_id)
            page=spec.pages[item['page_index']]
            workflow={'engine':spec.engine,'text_rendering':spec.text_rendering,'page':page.model_dump(),'reference_ids':spec.reference_ids}
            if _local(spec):
                with material_lock:
                    if owned_record('generation',gid,user_id)['status']!='pending':continue
                    image,source=render_material(paths[page.asset_id],page,output_size(spec),palette=spec.palette)
                    workflow.update(source_width=source['source_size'][0],source_height=source['source_size'][1],material_region_size=source['region_size'],placed_size=source['placed_size'],api_calls=0)
                    info=generation_service.save_png(image,output)
            else:
                inputs=[paths[page.asset_id],*[paths[aid] for aid in spec.reference_ids]]
                result=provider.edit_image(build_instruction(spec,item['page_index']),inputs,(1536,2048),spec.image_quality)
                if owned_record('generation',gid,user_id)['status']!='pending':continue
                from PIL import Image
                with Image.open(io.BytesIO(result['image_bytes'])) as source:
                    downloaded=generation_service.save_png(source,raw)
                workflow.update(native_width=downloaded.get('width'),native_height=downloaded.get('height'))
                workflow.update(api_calls=1,image_quality=spec.image_quality)
                info=generation_service.save_png(render_copy(raw,page,output_size(spec),text_rendering=spec.text_rendering),output)
            saved=_safe_update(gid,{'status':'completed','filename':info['filename'],'width':info['width'],
                                   'height':info['height'],'size_bytes':info['size_bytes'],'error':None,
                                   'workflow_json':json.dumps(workflow,ensure_ascii=False)})
            if saved and saved['status']!='completed':output.unlink(missing_ok=True)
        except Exception as exc:
            code=type(exc).__name__
            logger.warning('套图单页处理失败: %s; code=%s',gid,code)
            message=('本地素材排版或保存失败，请检查素材与磁盘后重试' if _local(spec) else '参考图生成或保存失败，请检查图像服务；未自动重复调用')
            if isinstance(exc,provider.ProviderError):message=str(exc)
            _safe_update(gid,{'status':'failed','error':message})
            output.unlink(missing_ok=True)
            # Stop the remaining set after any failed call; no surprise use of further quota.
            _cancel_pending(batch_id,user_id,exclude=gid)
            return
        finally:raw.unlink(missing_ok=True)


@router.get('')
def list_sets(user: CurrentUser):
    with closing(db.get_connection()) as con:
        rows=con.execute('SELECT batch_id FROM product_sets WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(user['user_id'],)).fetchall()
    return {'items':[_batch(row['batch_id'],user['user_id']) for row in rows]}


@router.get('/{batch_id}')
def get_set(batch_id: str,user: CurrentUser):return _batch(batch_id,user['user_id'])


def _cancel_pending(batch_id,user_id,exclude=''):
    with closing(db.get_connection()) as con,con:
        con.execute('BEGIN IMMEDIATE')
        ids=con.execute("SELECT generation_id FROM generations WHERE batch_id=? AND user=? AND status='pending' AND page_index>=0 AND generation_id!=?",(batch_id,user_id,exclude)).fetchall()
        for row in ids:
            con.execute("UPDATE generations SET status='cancelled',error='套图已停止；已提交的单页可能仍消耗上游额度' WHERE generation_id=?",(row['generation_id'],))
            settle(con,row['generation_id'],'cancelled')


@router.post('/{batch_id}/cancel')
def cancel_set(batch_id: str,user: CurrentUser):
    _batch(batch_id,user['user_id'])
    _cancel_pending(batch_id,user['user_id'])
    return _batch(batch_id,user['user_id'])


class Review(BaseModel):
    product_matches: bool
    copy_matches: bool
    no_extra_accessories: bool
    layout_matches: bool


class PageRetry(BaseModel):
    page: dict
    confirm_send: bool = False


@router.post('/{batch_id}/pages/{generation_id}/regenerate',status_code=201)
def regenerate_page(batch_id: str,generation_id: str,user: CurrentUser,payload: PageRetry):
    state=_batch(batch_id,user['user_id'])
    row=next((item for item in state['items'] if item['generation_id']==generation_id),None)
    if not row:raise HTTPException(404,'套图页面不存在')
    spec_data=state['spec']
    spec_data['pages'][row['page_index']]=payload.page
    try:
        spec=ProductSetSpec.model_validate(spec_data)
    except (ValueError,OSError):raise HTTPException(400,'本页标题、文案、素材或画面要求无效，请检查后重试')
    if not _local(spec):
        if not payload.confirm_send:raise HTTPException(400,'请确认再次发送图片与创作要求，单页重生成会重新计费')
        if not spec.image_quality:raise HTTPException(400,'原任务未选择图像质量，请新建任务')
        if not provider.available():raise HTTPException(503,provider.NOT_CONFIGURED)
    _validate(spec,user['user_id'])
    try:
        with closing(db.get_connection()) as con,con:
            con.execute('BEGIN IMMEDIATE')
            current=con.execute('SELECT * FROM generations WHERE generation_id=? AND batch_id=? AND user=? AND page_index>=0',(generation_id,batch_id,user['user_id'])).fetchone()
            if not current:raise HTTPException(409,'本页已更新，请刷新套图')
            if con.execute("SELECT 1 FROM generations WHERE batch_id=? AND status='pending' AND page_index>=0",(batch_id,)).fetchone():
                raise HTTPException(409,'套图正在生成，请等待完成或先停止')
            gid=uuid4().hex
            reserve_credit(con,user['user_id'],gid)
            archived=con.execute('SELECT COALESCE(MIN(page_index),0)-1 FROM generations WHERE batch_id=?',(batch_id,)).fetchone()[0]
            con.execute('UPDATE generations SET page_index=? WHERE generation_id=?',(min(-1,archived),generation_id))
            page=spec.pages[current['page_index']]
            stamp=datetime.now(timezone.utc).isoformat()
            width,height=output_size(spec)
            con.execute('''INSERT INTO generations
                (generation_id,user,asset_id,prompt,full_prompt,model,size,quality,status,created_at,
                 ratio,resolution,language,type,workflow_json,batch_id,page_index,review_status)
                VALUES (?,?,?,?,?,?,?,'standard','pending',?,'3:4',?,?,?, ?,?,?,'needs_review')''',
                (gid,user['user_id'],page.asset_id,spec.requirements,_brief(spec,current['page_index']),LOCAL_MODEL if _local(spec) else provider.MODEL,
                 f'{width}x{height}',stamp,spec.resolution,spec.language,'local_set' if _local(spec) else 'reference_set',
                 json.dumps({'engine':spec.engine,'text_rendering':spec.text_rendering,'page':page.model_dump(),'reference_ids':spec.reference_ids},ensure_ascii=False),batch_id,current['page_index']))
            con.execute('UPDATE product_sets SET spec_json=? WHERE batch_id=?',(spec.model_dump_json(),batch_id))
    except HTTPException:raise
    except Exception:
        logger.warning('套图重试保存失败: %s',batch_id)
        raise HTTPException(503,'本页任务暂时无法保存，请稍后重试')
    threading.Thread(target=_run_set,args=(batch_id,user['user_id']),daemon=True).start()
    return _batch(batch_id,user['user_id'])


@router.post('/{batch_id}/pages/{generation_id}/review')
def review_page(batch_id: str,generation_id: str,user: CurrentUser,payload: Review):
    state=_batch(batch_id,user['user_id'])
    row=next((item for item in state['items'] if item['generation_id']==generation_id),None)
    if not row or row['status']!='completed':raise HTTPException(400,'该页尚未生成完成')
    status='accepted' if all(payload.model_dump().values()) else 'rejected'
    with closing(db.get_connection()) as con,con:
        con.execute('UPDATE generations SET review_status=? WHERE generation_id=? AND user=?',(status,generation_id,user['user_id']))
    return _batch(batch_id,user['user_id'])


@router.get('/{batch_id}/download')
def download_set(batch_id: str,user: CurrentUser,long_edge: int=Query(default=2000)):
    state=_batch(batch_id,user['user_id'])
    if long_edge not in (1200,2000):raise HTTPException(400,'仅支持1200/2000导出；4K/8K已停用')
    items=state['items']
    if not items or any(item['status']!='completed' or item.get('review_status')!='accepted' for item in items):
        raise HTTPException(400,'请逐张核对商品、文案、配件和版式，再下载整套成品')
    if not export_lock.acquire(blocking=False):raise HTTPException(429,'正在导出其他图片，请稍后重试')
    temporary=None
    try:
        from PIL import Image, ImageOps
        generation_service.GENERATION_DIR.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='set-export-',dir=generation_service.GENERATION_DIR)
        root=Path(temporary.name)
        destination=root/'images.zip'
        metadata={'engine':state['spec'].get('engine','reference'),'export_size':[long_edge*3//4,long_edge],
                  'upscaled':any(_upscaled(item,long_edge) for item in items),
                  'review':'seller accepted','images':[]}
        with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_STORED) as archive:
            for item in items:
                source=generation_service.GENERATION_DIR/(item['generation_id']+'.png')
                if not source.is_file():raise HTTPException(404,'成品文件不存在，请重新生成该页')
                name=f"{item['page_index']+1:02d}.png"
                export=root/name
                with Image.open(source) as image:
                    ImageOps.fit(image.convert('RGB'),(long_edge*3//4,long_edge),method=Image.Resampling.LANCZOS).save(export,format='PNG')
                archive.write(export,name)
                workflow=item.get('workflow',{})
                metadata['images'].append({'file':name,'source_generation_id':item['generation_id'],
                    'native_ai_size':[workflow.get('native_width'),workflow.get('native_height')],
                    'material_region_size':workflow.get('material_region_size'),'placed_size':workflow.get('placed_size'),
                    'api_calls':workflow.get('api_calls'),'upscaled':_upscaled(item,long_edge),
                    'note':'放大导出不会增加素材细节' if workflow.get('engine')=='local' else ''})
                export.unlink()
            archive.writestr('export-info.json',json.dumps(metadata,ensure_ascii=False,indent=2))
        return FileResponse(destination,media_type='application/zip',filename=f'mhp-{batch_id}-{long_edge}.zip',background=BackgroundTask(temporary.cleanup))
    except Exception:
        if temporary:temporary.cleanup()
        raise
    finally:export_lock.release()
