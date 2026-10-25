from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.models import db
from app.services.storage_service import UPLOAD_DIR


def now():
    return datetime.now(timezone.utc).isoformat()


def owned_folder(folder_id, user_id):
    with closing(db.get_connection()) as con:
        row = con.execute('SELECT * FROM reference_folders WHERE folder_id=? AND user_id=?',
                          (folder_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, '示例图文件夹不存在')
    return dict(row)


def folder_for_source(user_id, source_url, name):
    with closing(db.get_connection()) as con, con:
        con.execute('INSERT OR IGNORE INTO reference_folders VALUES (?,?,?,?,?)',
                    (uuid4().hex, user_id, name[:120], source_url, now()))
        row = con.execute('SELECT * FROM reference_folders WHERE user_id=? AND source_url=?',
                          (user_id, source_url)).fetchone()
    folder = dict(row)
    (UPLOAD_DIR / 'references' / folder['folder_id']).mkdir(parents=True, exist_ok=True)
    return folder
