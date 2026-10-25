"""Small file journal for terminal task updates while SQLite is unavailable."""
from contextlib import closing
import json
import logging
from app.models import db

logger = logging.getLogger(__name__)


def directory():
    return db.DB_PATH.parent / (db.DB_PATH.stem + '-recovery')


def remember(generation_id, updates):
    root = directory()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (generation_id + '.json')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(updates, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def reconcile():
    for path in directory().glob('*.json'):
        try:
            updates = json.loads(path.read_text(encoding='utf-8'))
            fields = {k: v for k, v in updates.items() if k in ('status', 'error', 'filename', 'width', 'height', 'size_bytes', 'task_id','workflow_json')}
            with closing(db.get_connection()) as con, con:
                con.execute(f"UPDATE generations SET {', '.join(k+'=?' for k in fields)} WHERE generation_id=? AND status='pending'", (*fields.values(), path.stem))
                row=con.execute('SELECT status FROM generations WHERE generation_id=?',(path.stem,)).fetchone()
                if row and row['status'] in ('completed','failed','cancelled'):
                    from app.services.credit_service import settle
                    settle(con,path.stem,row['status'])
            path.unlink()
        except Exception:
            logger.exception('任务状态恢复暂不可用')


def interrupted_on_startup():
    reconcile()
    with closing(db.get_connection()) as con, con:
        con.execute("DELETE FROM requests WHERE response IS NULL")
        con.execute("UPDATE generations SET status='failed', error='服务已重启，任务中断。上游可能已处理，请确认后重新生成' WHERE status='pending'")
        from app.services.credit_service import settle
        for row in con.execute("SELECT h.generation_id,g.status FROM credit_holds h JOIN generations g ON h.generation_id=g.generation_id WHERE h.state='reserved' AND g.status IN ('completed','failed','cancelled')").fetchall():
            settle(con,row['generation_id'],row['status'])
