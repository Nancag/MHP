"""Root-owned host worker. UI can request only fixed backup/restore operations."""
import argparse
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import time
from contextlib import closing
from pathlib import Path
from uuid import uuid4

SITE=Path('/opt/mhp')
STORE=Path('/opt/mhp-backups/automatic')
OPS=Path('/opt/mhp-operations')
COMPOSE=['docker','compose','-f',str(SITE/'compose.json')]
INCLUDE=('app','frontend','deploy','extensions','compose.json','.env','.dockerignore','requirements-cloud.txt','requirements-cloud.lock','data')
AI_SECRET_ASSIGNMENT=re.compile(r'^\s*(?:export\s+)?(?:MHP_TEXT_API_KEY|MHP_IMAGE_API_KEY)\s*=')


def sanitized_env(content):
    """Keep other settings verbatim; omit all assignments of the two new AI keys.

    MHP's environment loader supports single-line values. No secret-bearing
    temporary file is created while building the backup.
    """
    text=content.decode('utf-8-sig')
    return ''.join(line for line in text.splitlines(keepends=True)
                   if not AI_SECRET_ASSIGNMENT.match(line)).encode('utf-8')

def run(args):
    return subprocess.run(args,cwd=SITE,check=True,capture_output=True,text=True).stdout.strip()

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temp.replace(path)

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024**2),b''):h.update(chunk)
    return h.hexdigest()

def metadata(bid):
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}',bid):raise ValueError('Invalid backup ID')
    value=json.loads((STORE/(bid+'.json')).read_text())
    if value['backup_id']!=bid:raise ValueError('Invalid backup metadata')
    return value

def index():
    values=[]
    for p in sorted(STORE.glob('*.json'),reverse=True):
        try:
            v=json.loads(p.read_text());values.append({k:v[k] for k in ('backup_id','created_at','bytes','sha256','kind')})
        except (ValueError,KeyError):continue
    write(OPS/'index.json',values)

def ready():
    for _ in range(80):
        try:
            if run(['docker','inspect','--format','{{.State.Health.Status}}','mhp-api-1'])=='healthy':return
        except subprocess.CalledProcessError:pass
        time.sleep(3)
    raise RuntimeError('API did not become healthy')

def backup(kind='manual'):
    bid=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid4().hex[:8]
    path=STORE/(bid+'.tar.gz');partial=path.with_suffix('.partial')
    images={service:run(['docker','inspect','--format','{{.Image}}',f'mhp-{service}-1']) for service in ('api','web')}
    stopped=False
    try:
        stopped=True;run(COMPOSE+['stop','api','web'])
        def select(member):
            p=Path(member.name)
            excluded=('.cache','.numba-cache','__pycache__','operations','backups')
            if p.parts[:2]==('data','models') or any(v in p.parts for v in excluded) or member.issym() or member.islnk():return None
            return member
        with tarfile.open(partial,'w:gz',compresslevel=3) as archive:
            for name in INCLUDE:
                source=SITE/name
                if not source.exists():continue
                if name=='.env':
                    if source.is_symlink():continue
                    content=sanitized_env(source.read_bytes())
                    info=archive.gettarinfo(str(source),arcname=name)
                    info.size=len(content);info.mode=0o600
                    archive.addfile(info,io.BytesIO(content))
                else:archive.add(source,arcname=name,filter=select)
        partial.replace(path);path.chmod(0o600)
        record={'backup_id':bid,'created_at':int(time.time()),'bytes':path.stat().st_size,'sha256':digest(path),'kind':kind,'images':images}
        for service,image in images.items():run(['docker','tag',image,f'mhp-backup-{service}:{bid.lower()}'])
        write(STORE/(bid+'.json'),record)
    finally:
        if stopped:run(COMPOSE+['start','api','web'])
        partial.unlink(missing_ok=True)
    # Keep seven scheduled/manual backups; preserve pre-restore safety snapshots separately.
    ordinary=[p for p in sorted(STORE.glob('*.json'),reverse=True) if json.loads(p.read_text()).get('kind')!='pre-restore']
    for old in ordinary[7:]:
        value=json.loads(old.read_text());(STORE/(value['backup_id']+'.tar.gz')).unlink(missing_ok=True);old.unlink()
        for service in ('api','web'):
            subprocess.run(['docker','image','rm',f"mhp-backup-{service}:{value['backup_id'].lower()}"],capture_output=True)
    index();return bid

def restore(bid,safety=True):
    record=metadata(bid);archive_path=STORE/(bid+'.tar.gz')
    if digest(archive_path)!=record['sha256']:raise ValueError('Backup checksum mismatch')
    for image in record['images'].values():run(['docker','image','inspect',image])
    before=backup('pre-restore') if safety else None
    with tempfile.TemporaryDirectory(prefix='mhp-restore-',dir=SITE.parent) as folder:
        stage=Path(folder)
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                p=Path(member.name)
                if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] not in INCLUDE or member.issym() or member.islnk() or not(member.isfile() or member.isdir()):raise ValueError('Unsafe backup member')
            archive.extractall(stage,filter='data')
        database=stage/'data/mhp.db'
        with closing(sqlite3.connect(database)) as con,con:
            if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid database')
            con.execute('DELETE FROM auth_sessions');con.execute('DELETE FROM auth_codes')
        stopped=False
        try:
            stopped=True;run(COMPOSE+['stop','api','web'])
            # Replace backed-up trees, carrying forward reinstallable model files/cache.
            for name in INCLUDE:
                source=stage/name;target=SITE/name
                if not source.exists():continue
                if source.is_dir():
                    old=stage/('previous-'+name.replace('/','_'))
                    if target.exists():target.rename(old)
                    if name=='data' and old.exists():
                        for keep in ('models','.numba-cache','.cache'):
                            if (old/keep).exists():shutil.move(str(old/keep),str(source/keep))
                    shutil.move(str(source),str(target))
                else:shutil.copy2(source,target)
            for p in [SITE/'data',*(SITE/'data').rglob('*')]:
                if not p.is_symlink():os.chown(p,10001,10001)
            (SITE/'.env').chmod(0o600)
            for service,image in record['images'].items():run(['docker','tag',image,f'mhp-{service}:latest'])
            run(COMPOSE+['up','-d','--no-build','api','web']);ready();stopped=False
        except Exception:
            if before:
                restore(before,safety=False)
            elif stopped:
                run(COMPOSE+['up','-d','--no-build','api','web'])
            raise
    index();return bid

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scheduled',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Host worker requires root')
    STORE.mkdir(parents=True,exist_ok=True);STORE.chmod(0o700)
    OPS.mkdir(parents=True,exist_ok=True)
    for name in ('requests','results','active'):(OPS/name).mkdir(exist_ok=True)
    with Path('/run/lock/mhp-backup.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        (OPS/'heartbeat').touch()
        if args.scheduled:backup('scheduled');return
        index()
        for request in sorted((OPS/'requests').glob('*.json'))[:1]:
            if request.is_symlink() or request.stat().st_size>8192:request.unlink();continue
            active=OPS/'active'/request.name;request.replace(active)
            value={}
            try:
                value=json.loads(active.read_text())
                oid=value['operation_id']
                if not re.fullmatch('[0-9a-f]{32}',oid) or request.stem!=oid:raise ValueError('Invalid operation')
                value['state']='running';write(OPS/'results'/request.name,value)
                if value['action']=='backup':bid=backup()
                elif value['action']=='restore' and value.get('confirmation')=='恢复整站':bid=restore(value['backup_id'])
                else:raise ValueError('Unsupported operation')
                value.update(state='completed',message='操作成功',backup_id=bid)
            except Exception as e:
                value.update(state='failed',message='操作失败：'+type(e).__name__+'；请管理员检查主机日志')
                print(type(e).__name__,str(e)[:180],flush=True)
            finally:
                value['finished_at']=int(time.time());write(OPS/'results'/request.name,value);active.unlink(missing_ok=True)
                (OPS/'heartbeat').touch()

if __name__=='__main__':main()
