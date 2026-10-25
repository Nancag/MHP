"""Apply new capability settings while preserving existing cloud credentials."""
import json
from pathlib import Path
root=Path('/opt/mhp');env=root/'.env';lines=env.read_text().splitlines()
config=Path('/root/mhp-config-update.json')
values=json.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
allowed=set()  # No provider credentials are accepted.
assert not set(values)-allowed
assert all(isinstance(v,str) and '\n' not in v and '\r' not in v for v in values.values())
values.update(MHP_ADMIN_EMAILS='18965717093@163.com',MHP_OPERATIONS_DIR='/operations',AUTH_COOKIE_SECURE='1',AUTH_ALLOWED_ORIGINS='https://118.178.92.58')
existing={line.split('=',1)[0] for line in lines if '=' in line and not line.startswith('#')}
lines=[line for line in lines if not line.strip().startswith(('DASHSCOPE_','IMAGE_EDIT_'))]
lines=[line.split('=',1)[0]+'='+values[line.split('=',1)[0]] if '=' in line and line.split('=',1)[0] in values else line for line in lines]
lines += [k+'='+v for k,v in values.items() if k not in existing]
env.write_text('\n'.join(lines)+'\n');env.chmod(0o600)
path=root/'compose.json';compose=json.loads(path.read_text());api=compose['services']['api']
volumes=api.setdefault('volumes',[])
if not any('/opt/mhp-operations:' in v for v in volumes):volumes.append('/opt/mhp-operations:/operations')
api.setdefault('environment',{})['MHP_OPERATIONS_DIR']='/operations'
path.write_text(json.dumps(compose,indent=2)+'\n')
config.unlink(missing_ok=True)
print('CONFIG_APPLIED: retired provider settings removed; admin and operations enabled')
