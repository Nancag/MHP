"""Read only deployment metadata; omit environment values and user records."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path('/opt/mhp')
compose = root / 'compose.json'
config = json.loads(compose.read_text())
output = {'root': str(root), 'services': {}}
for name in ['web', 'api']:
    container = subprocess.check_output(['docker', 'compose', '-f', str(compose), 'ps', '-q', name], text=True).strip()
    record = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
    output['services'][name] = {'id': container, 'status': record['State']['Status'], 'started': record['State']['StartedAt'],
                               'mounts': [{'source': mount['Source'], 'destination': mount['Destination']} for mount in record['Mounts']]}
web = output['services']['web']['id']
cloud_index = subprocess.check_output(['docker', 'exec', web, 'cat', '/srv/mhp/index.html'])
host_index = (root / 'frontend/dist/index.html').read_bytes()
output['host_index_sha256'] = hashlib.sha256(host_index).hexdigest()
output['cloud_index_sha256'] = hashlib.sha256(cloud_index).hexdigest()
output['web_ports'] = config['services']['web'].get('ports', [])
output['download_already_present'] = subprocess.run(['docker', 'exec', web, 'test', '-f', '/srv/mhp/download.html']).returncode == 0
print(json.dumps(output, indent=2))
