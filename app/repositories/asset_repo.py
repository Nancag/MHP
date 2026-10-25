from datetime import datetime, timezone

from app.models.db import get_connection


def create_asset(asset: dict) -> dict:
    """将图片信息写入数据库，成功后返回完整记录。"""

    record = {
        **asset,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO assets (
                asset_id,
                filename,
                width,
                height,
                format,
                size_bytes,
                created_at,
                user_id
                ,role,folder_id,source_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["asset_id"],
                record["filename"],
                record["width"],
                record["height"],
                record["format"],
                record["size_bytes"],
                record["created_at"],
                record.get("user_id"),
                record.get('role','product'),
                record.get('folder_id'),
                record.get('source_url'),
            ),
        )
        connection.commit()
        return record

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
def list_assets(page: int, page_size: int, user_id: str, role: str | None = None) -> dict:
    """按上传时间从新到旧，分页查询素材。"""

    offset = (page - 1) * page_size
    connection = get_connection()
    where = 'user_id = ? AND deleted_at IS NULL'
    args = [user_id]
    if role is not None:
        where += ' AND role = ?'
        args.append(role)

    try:
        total = connection.execute(
            'SELECT COUNT(*) FROM assets WHERE ' + where, args
        ).fetchone()[0]

        rows = connection.execute(
            """
            SELECT
                asset_id,
                filename,
                width,
                height,
                format,
                size_bytes,
                created_at
                ,role,folder_id,source_url
            FROM assets
            WHERE """ + where + """
            ORDER BY created_at DESC, asset_id DESC
            LIMIT ? OFFSET ?
            """,
            (*args, page_size, offset),
        ).fetchall()

        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    finally:
        connection.close()
