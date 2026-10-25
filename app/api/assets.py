import logging
import os
import re
import sqlite3
import time
from contextlib import closing
from app.models import db
from threading import Lock

_ASSET_MUTATION_LOCK = Lock()

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from typing import Literal
from fastapi.responses import FileResponse

from app.repositories.asset_repo import create_asset, list_assets
from app.api.auth import CurrentUser
from app.repositories.ownership import owned_record
from app.services.storage_service import (
    MAX_FILE_BYTES,
    UPLOAD_DIR,
    save_product_image,
)
from app.services.storage_quota import StorageQuotaExceeded
from app.services.library_service import owned_folder


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assets", tags=["商品图片"])


def trash_retention_days():
    raw = os.environ.get("MHP_TRASH_RETENTION_DAYS", "30").strip()
    try:
        value = int(raw)
    except ValueError:
        return 30
    return value if value >= 0 else 30


def _remove_empty_trash_parents(path):
    trash_root = (UPLOAD_DIR.parent / 'trash').resolve()
    parent = path.parent.resolve()
    while parent != trash_root and parent.is_relative_to(trash_root):
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def purge_expired_trash():
    """Permanently remove trash items past the configured retention period."""
    days = trash_retention_days()
    if days == 0 or not _ASSET_MUTATION_LOCK.acquire(blocking=False):
        return 0
    removed = 0
    try:
        cutoff = int(time.time()) - days * 86400
        with closing(db.get_connection()) as con:
            rows = con.execute(
                """SELECT asset_id,filename FROM assets
                   WHERE deleted_at IS NOT NULL AND deleted_at < ?
                   ORDER BY deleted_at LIMIT 200""",
                (cutoff,),
            ).fetchall()
        for row in rows:
            with closing(db.get_connection()) as con, con:
                con.execute('BEGIN IMMEDIATE')
                current = con.execute(
                    """SELECT filename FROM assets
                       WHERE asset_id=? AND deleted_at IS NOT NULL AND deleted_at < ?""",
                    (row['asset_id'], cutoff),
                ).fetchone()
                if not current:
                    continue
                path = UPLOAD_DIR.parent / 'trash' / current['filename']
                trash_root = (UPLOAD_DIR.parent / 'trash').resolve()
                if not path.resolve().is_relative_to(trash_root):
                    logger.error("拒绝清理越界回收站路径: %s", row['asset_id'])
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.exception("回收站文件永久删除失败: %s", row['asset_id'])
                    continue
                con.execute('DELETE FROM assets WHERE asset_id=?', (row['asset_id'],))
            _remove_empty_trash_parents(path)
            removed += 1
    finally:
        _ASSET_MUTATION_LOCK.release()
    return removed


@router.get('/trash')
def trash(user:CurrentUser):
    with closing(db.get_connection()) as con:
        return {'items':[dict(r) for r in con.execute('SELECT asset_id,filename,role,deleted_at FROM assets WHERE user_id=? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC',(user['user_id'],))]}

@router.delete('/{asset_id}')
def delete_asset(asset_id:str,user:CurrentUser):
    if not re.fullmatch(r'[0-9a-f]{32}',asset_id):raise HTTPException(400,'素材编号无效')
    if not _ASSET_MUTATION_LOCK.acquire(blocking=False):raise HTTPException(409,'正在处理素材，请稍后再删除')
    moved=False;source=None;destination=None
    try:
        with closing(db.get_connection()) as con,con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM assets WHERE asset_id=? AND user_id=? AND deleted_at IS NULL',(asset_id,user['user_id'])).fetchone()
            if not row:raise HTTPException(404,'素材不存在')
            if con.execute("SELECT 1 FROM generations WHERE user=? AND status='pending' AND (asset_id=? OR workflow_json LIKE ?) LIMIT 1",(user['user_id'],asset_id,'%'+asset_id+'%')).fetchone():raise HTTPException(409,'素材正在用于生成，请任务完成后再删除')
            source=UPLOAD_DIR/row['filename'];destination=UPLOAD_DIR.parent/'trash'/row['filename']
            destination.parent.mkdir(parents=True,exist_ok=True)
            if source.exists():source.replace(destination);moved=True
            con.execute('UPDATE assets SET deleted_at=? WHERE asset_id=?',(int(time.time()),asset_id))
        days = trash_retention_days()
        message = '已移入回收站；已有生成结果保留' if days == 0 else f'已移入回收站，{days} 天后自动永久删除；已有生成结果保留'
        return {'deleted':True,'recoverable':True,'retention_days':days,'message':message}
    except Exception:
        if moved and destination and destination.exists():destination.replace(source)
        raise
    finally:_ASSET_MUTATION_LOCK.release()

@router.post('/{asset_id}/restore')
def restore_asset(asset_id:str,user:CurrentUser):
    with closing(db.get_connection()) as con,con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM assets WHERE asset_id=? AND user_id=? AND deleted_at IS NOT NULL',(asset_id,user['user_id'])).fetchone()
        if not row:raise HTTPException(404,'回收站素材不存在')
        source=UPLOAD_DIR.parent/'trash'/row['filename'];destination=UPLOAD_DIR/row['filename']
        if not source.is_file():raise HTTPException(404,'原图文件缺失，请联系管理员从备份恢复')
        source.replace(destination)
        try:
            con.execute('UPDATE assets SET deleted_at=NULL WHERE asset_id=?',(asset_id,));con.commit()
        except Exception:
            destination.replace(source);raise
    return {'restored':True}

@router.get("")
def get_assets(
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: Literal['product', 'reference'] | None = Query(default=None),
):
    """分页查询已登记的商品图片。"""

    try:
        result = list_assets(page=page, page_size=page_size, user_id=user["user_id"], role=role)
    except sqlite3.Error as exc:
        logger.exception("查询素材列表失败")
        raise HTTPException(
            status_code=500,
            detail="素材列表读取失败，请查看后端日志",
        ) from exc

    for item in result["items"]:
        asset_id = item["asset_id"]
        item["preview_url"] = f"/api/assets/{asset_id}/preview"

    return result


@router.post("", status_code=201)
def upload_asset(user: CurrentUser, file: UploadFile = File(...), role: Literal['product','reference'] = Form('product'), folder_id: str | None = Form(None)):
    """上传商品图片，保存文件并登记数据库记录。"""

    try:
        if folder_id:
            if role != 'reference':
                raise HTTPException(400, '商品原图不能上传至示例图文件夹')
            owned_folder(folder_id, user['user_id'])
        image_bytes = file.file.read(MAX_FILE_BYTES + 1)

        if len(image_bytes) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="图片不能超过 10 MB",
            )

        try:
            result = save_product_image(image_bytes, folder_id=folder_id or None)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc
        except OSError as exc:
            logger.exception("图片保存失败")
            raise HTTPException(
                status_code=500,
                detail="图片保存失败，请检查存储空间和目录权限",
            ) from exc

        # 文件保存成功后，将素材信息写入数据库。
        try:
            result = create_asset({**result, "user_id": user["user_id"], 'role':role, 'folder_id':folder_id or None})
        except StorageQuotaExceeded as exc:
            file_path = UPLOAD_DIR / result["filename"]
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("清理超出配额的图片失败")
            raise HTTPException(status_code=507, detail=str(exc)) from exc
        except sqlite3.Error as exc:
            logger.exception("素材信息写入数据库失败")

            # 数据库登记失败时，尝试清理本次新保存的图片。
            file_path = UPLOAD_DIR / result["filename"]
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("清理未登记的图片失败")

            raise HTTPException(
                status_code=500,
                detail="素材记录保存失败，请查看后端日志",
            ) from exc

        asset_id = result["asset_id"]
        result["preview_url"] = f"/api/assets/{asset_id}/preview"
        return result

    finally:
        file.file.close()


@router.get("/{asset_id}/preview")
def preview_asset(asset_id: str, user: CurrentUser):
    """根据素材编号预览已保存的商品图片。"""

    if not re.fullmatch(r"[0-9a-f]{32}", asset_id):
        raise HTTPException(
            status_code=400,
            detail="素材编号格式不正确",
        )

    record = owned_record("asset", asset_id, user["user_id"])
    for extension, media_type in (
        (".jpg", "image/jpeg"),
        (".png", "image/png"),
    ):
        file_path = UPLOAD_DIR / record['filename']

        if file_path.suffix.lower() == extension and file_path.is_file() and file_path.resolve().is_relative_to(UPLOAD_DIR.resolve()):
            return FileResponse(
                path=file_path,
                media_type=media_type,
            )

    raise HTTPException(
        status_code=404,
        detail="图片不存在",
    )
