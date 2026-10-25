from fastapi import HTTPException
from app.models.db import get_connection


def owned_record(kind, record_id, user_id):
    table, key, owner = {
        "asset": ("assets", "asset_id", "user_id"),
        "generation": ("generations", "generation_id", "user"),
    }[kind]
    connection = get_connection()
    try:
        row = connection.execute(f"SELECT * FROM {table} WHERE {key} = ? AND {owner} = ?",
                                 (record_id, user_id)).fetchone()
        if not row or (kind == 'asset' and row['deleted_at'] is not None):
            raise HTTPException(404, "记录不存在")
        return dict(row)
    finally:
        connection.close()
