from datetime import datetime, timezone

from app.models.db import get_connection
from app.repositories.recovery import reconcile
from app.services.parameters import aliases


_GENERATION_COLUMNS = """
    generation_id,
    asset_id,
    cutout_id,
    task_id,
    prompt,
    full_prompt,
    model,
    size,
    quality,
    filename,
    width,
    height,
    size_bytes,
    status,
    error,
    cost_usd,
    created_at,
    user,
    ratio,
    resolution,
    language,
    platform,
    scene,
    style,
    type,
    design_json,
    workflow_json,
    batch_id,
    page_index,
    review_status
"""


def create_generation(generation: dict) -> dict:
    """将生图任务记录写入数据库，成功后返回完整记录。"""

    record = {
        **generation,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    connection = get_connection()

    try:
        if generation.get('charge_credit'):
            from app.services.credit_service import reserve_credit
            connection.execute('BEGIN IMMEDIATE')
            reserve_credit(connection, record['user'], record['generation_id'])
        connection.execute(
            """
            INSERT INTO generations (
                generation_id,
                asset_id,
                cutout_id,
                task_id,
                prompt,
                full_prompt,
                model,
                size,
                quality,
                filename,
                width,
                height,
                size_bytes,
                status,
                error,
                cost_usd,
                created_at,
                user,
                ratio,
                resolution,
                language,
                platform,
                scene,
                style,
                type,
                design_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["generation_id"],
                record.get("asset_id"),
                record.get("cutout_id"),
                record.get("task_id"),
                record["prompt"],
                record.get("full_prompt"),
                record["model"],
                record["size"],
                record.get("quality"),
                record.get("filename"),
                record.get("width"),
                record.get("height"),
                record.get("size_bytes"),
                record["status"],
                record.get("error"),
                record.get("cost_usd"),
                record["created_at"],
                record.get("user", "anonymous"),
                record.get("ratio"),
                record.get("resolution"),
                record.get("language"),
                record.get("platform"),
                record.get("scene"),
                record.get("style"),
                record.get("type", "ai_generation"),
                record.get('design_json'),
            ),
        )
        connection.commit()
        record.pop('charge_credit',None)
        return record

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_generation(generation_id: str):
    """按编号查询生图任务记录；不存在时返回 None。"""

    reconcile()
    connection = get_connection()

    try:
        row = connection.execute(
            f"SELECT {_GENERATION_COLUMNS} FROM generations WHERE generation_id = ?",
            (generation_id,),
        ).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def update_generation(generation_id: str, updates: dict):
    """更新生图任务记录的可变字段；不存在时返回 None。"""

    connection = get_connection()

    try:
        existing = connection.execute(
            f"SELECT {_GENERATION_COLUMNS} FROM generations WHERE generation_id = ?",
            (generation_id,),
        ).fetchone()

        if not existing:
            return None

        allowed_fields = (
            'workflow_json',
            "task_id",
            "filename",
            "width",
            "height",
            "size_bytes",
            "status",
            "error",
            "cost_usd",
            "user",
            "ratio",
            "resolution",
            "language",
            "platform",
            "scene",
            "style",
            "type",
        )

        fields = []
        values = []
        for key in allowed_fields:
            if key in updates:
                fields.append(f"{key} = ?")
                values.append(updates[key])

        if not fields:
            return dict(existing)

        values.append(generation_id)
        # Submission may return after cancellation. Keep the upstream id for tracking,
        # while all status/result updates remain conditional on pending.
        condition = "status IN ('pending', 'cancelled')" if set(updates) == {'task_id'} else "status = 'pending'"
        connection.execute(
            f"UPDATE generations SET {', '.join(fields)} WHERE generation_id = ? AND {condition}",
            values,
        )
        if updates.get('status') in ('completed','failed','cancelled'):
            current = connection.execute('SELECT status FROM generations WHERE generation_id=?',(generation_id,)).fetchone()
            if current and current['status']==updates['status']:
                from app.services.credit_service import settle
                settle(connection,generation_id,current['status'])
        connection.commit()

        row = connection.execute(
            f"SELECT {_GENERATION_COLUMNS} FROM generations WHERE generation_id = ?",
            (generation_id,),
        ).fetchone()

        return dict(row) if row else None

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def list_generations(
    asset_id: str = None,
    gen_type: str = None,
    scene: str = None,
    platform: str = None,
    style: str = None,
    page: int = 1,
    page_size: int = 20,
    user_id: str = None,
) -> dict:
    """分页查询生图历史，支持多维度过滤，从新到旧。"""

    reconcile()
    offset = (page - 1) * page_size
    connection = get_connection()

    where_clauses = []
    params = []
    if user_id is not None:
        where_clauses.append("user = ?")
        params.append(user_id)

    if asset_id:
        where_clauses.append("asset_id = ?")
        params.append(asset_id)
    if gen_type:
        where_clauses.append("type = ?")
        params.append(gen_type)
    for field, value in [('scene', scene), ('platform', platform), ('style', style)]:
        if value:
            values = aliases(field, value)
            where_clauses.append(f"{field} COLLATE NOCASE IN ({','.join('?' for _ in values)})")
            params.extend(values)

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    try:
        total = connection.execute(
            f"SELECT COUNT(*) AS total FROM generations{where_sql}",
            params,
        ).fetchone()["total"]

        rows = connection.execute(
            f"""
            SELECT {_GENERATION_COLUMNS}
            FROM generations
            {where_sql}
            ORDER BY created_at DESC, generation_id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, offset),
        ).fetchall()

        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    finally:
        connection.close()
