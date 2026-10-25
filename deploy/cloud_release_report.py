import hashlib,json,subprocess,tarfile
from pathlib import Path
root=Path('/opt/mhp')
index=json.loads(Path('/opt/mhp-operations/index.json').read_text())
latest=index[0];archive=Path('/opt/mhp-backups/automatic')/(latest['backup_id']+'.tar.gz')
with tarfile.open(archive) as a:
    names=a.getnames();assert 'app/models/db.py' in names and 'data/mhp.db' in names and '.env' in names
    assert not any(n.startswith('data/models/') for n in names)
operations=[json.loads(p.read_text()) for p in Path('/opt/mhp-operations/results').glob('*.json')]
report={'version':'2026.10.18-workspace.1','backups':len(index),'latest_backup':latest['backup_id'],
    'backup_contains_code_database_and_private_config':True,'reinstallable_models_excluded':True,
    'backup_operations':[{'action':v['action'],'state':v['state']} for v in operations],
    'html_sha256':hashlib.sha256((root/'frontend/dist/index.html').read_bytes()).hexdigest(),
    'timers':subprocess.check_output(['systemctl','list-timers','mhp-nightly-backup.timer','--no-pager'],text=True).strip(),
    'api_healthy':subprocess.check_output(['docker','inspect','--format','{{.State.Health.Status}}','mhp-api-1'],text=True).strip(),
    'models':len(list((root/'data/models').rglob('*.onnx')))}
print(json.dumps(report,ensure_ascii=False))
