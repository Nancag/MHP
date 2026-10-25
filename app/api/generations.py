"""Historical result access. External AI and cutout-dependent creation have been removed."""
import json
import logging
import re
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from app.api.auth import CurrentUser
from app.repositories.generation_repo import get_generation, list_generations, update_generation
from app.repositories.recovery import remember, reconcile
from app.repositories.ownership import owned_record
from app.services.generation_service import GENERATION_DIR, PROVIDER_REMOVED_MESSAGE
from app.services.parameters import normalize

logger=logging.getLogger(__name__)
router=APIRouter(prefix='/api/generations',tags=['图片历史'])

@router.post('')
def create_generation_route(user:CurrentUser):
    raise HTTPException(503,PROVIDER_REMOVED_MESSAGE)

def _safe_update(generation_id, updates):
    try:
        return update_generation(generation_id, updates)
    except Exception:
        logger.exception("任务状态写入失败，保存恢复日志")
        remember(generation_id, updates)
        return None


def _preview(record):
    if record:
        record['workflow'] = json.loads(record['workflow_json']) if record.get('workflow_json') else None
        record.pop('workflow_json', None)
        record['design'] = json.loads(record['design_json']) if record.get('design_json') else None
        record.pop('design_json', None)
        for field in ('language', 'platform', 'scene', 'style'):
            record[field] = normalize({field: record.get(field)})[field]
        if record['status'] == 'failed':
            from app.services.reference_service import public_error
            if record.get('type')=='local_set':
                record['error']='本地素材排版或保存失败，请检查素材与磁盘后重试'
            elif record.get('type')=='reference_set':
                record['error']=public_error(record.get('error'))
            else:
                record['error'] = 'AI 任务等待超时，请稍后重试' if '超时' in (record.get('error') or '') else '图片生成或保存失败，请确认上游状态后重试'
    if record and record.get('filename') and record['status'] == 'completed':
        record['preview_url'] = f"/api/generations/{record['generation_id']}/preview"
    return record


@router.post('/{generation_id}/cancel')
def cancel_generation_route(generation_id: str, user: CurrentUser):
    _valid_id(generation_id)
    record = owned_record('generation', generation_id, user['user_id'])
    if record['status'] == 'pending':
        record = update_generation(generation_id, {'status': 'cancelled', 'error': '已取消本地处理；上游任务可能继续运行及消耗额度'})
    return _preview(record)


def _valid_id(value):
    if not re.fullmatch(r'[0-9a-f]{32}', value):
        raise HTTPException(400, '任务编号格式不正确')


@router.get("")
def list_generations_route(
    user: CurrentUser,
    asset_id: str = Query(default=None),
    gen_type: str = Query(default=None),
    scene: str = Query(default=None),
    platform: str = Query(default=None),
    style: str = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """分页查询生图历史，支持按 asset_id / 类型 / 场景 / 平台 / 风格 过滤。"""

    if asset_id is not None:
        if not re.fullmatch(r"[0-9a-f]{32}", asset_id):
            raise HTTPException(status_code=400, detail="素材编号格式不正确")

    result = list_generations(
        asset_id=asset_id,
        gen_type=gen_type,
        scene=scene,
        platform=platform,
        style=style,
        page=page,
        page_size=page_size,
        user_id=user["user_id"],
    )

    for item in result["items"]:
        _preview(item)

    return result


@router.get("/{generation_id}/preview")
def preview_generation_route(generation_id: str, user: CurrentUser):
    """预览生图结果。"""

    if not re.fullmatch(r"[0-9a-f]{32}", generation_id):
        raise HTTPException(status_code=400, detail="任务编号格式不正确")

    record = owned_record("generation", generation_id, user["user_id"])
    if record["status"] != "completed":
        raise HTTPException(404, "结果尚不可用")
    file_path = GENERATION_DIR / f"{generation_id}.png"

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="生图结果不存在")

    return FileResponse(path=file_path, media_type="image/png")


@router.get("/{generation_id}")
def get_generation_route(generation_id: str, user: CurrentUser):
    """查询单个生图任务的状态。"""

    if not re.fullmatch(r"[0-9a-f]{32}", generation_id):
        raise HTTPException(status_code=400, detail="任务编号格式不正确")

    reconcile()
    record = owned_record("generation", generation_id, user["user_id"])
    if not record:
        raise HTTPException(status_code=404, detail="生图任务不存在")

    return _preview(record)
