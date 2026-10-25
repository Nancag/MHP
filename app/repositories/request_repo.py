"""SQLite request reservations prevent duplicate work, including across processes."""
from contextlib import closing
import hashlib
import json
import time
from fastapi import HTTPException
from app.models.db import get_connection


def reserve(kind, user_id, payload, request_id=None):
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    key = request_id or digest
    with closing(get_connection()) as con, con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM requests WHERE kind=? AND user_id=? AND request_key=?', (kind, user_id, key)).fetchone()
        if row:
            if row['payload_hash'] != digest:
                raise HTTPException(409, '同一请求编号不能用于不同参数')
            if row['response']:
                return key, json.loads(row['response'])
            raise HTTPException(409, '相同请求正在处理，请稍后查看历史，不要重复提交')
        con.execute('INSERT INTO requests VALUES (?, ?, ?, ?, ?, NULL)', (kind, user_id, key, digest, int(time.time())))
    return key, None


def finish(kind, user_id, key, response):
    with closing(get_connection()) as con, con:
        con.execute('UPDATE requests SET response=? WHERE kind=? AND user_id=? AND request_key=?', (json.dumps(response, ensure_ascii=False), kind, user_id, key))


def release(kind, user_id, key):
    with closing(get_connection()) as con, con:
        con.execute('DELETE FROM requests WHERE kind=? AND user_id=? AND request_key=?', (kind, user_id, key))
