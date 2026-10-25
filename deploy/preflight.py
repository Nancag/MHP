"""Read-only deployment checks; Python 3.10+ on the host, no third-party dependencies."""
import argparse
import ast
import hashlib
import json
import platform
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', action='store_true')
    parser.add_argument('--models', action='store_true')
    args = parser.parse_args()
    for folder in ('app', 'deploy', 'launcher', 'desktop/windows'):
        for source in (ROOT / folder).rglob('*.py'):
            ast.parse(source.read_text(encoding='utf-8-sig'), filename=str(source))
    config = json.loads((ROOT / 'compose.json').read_text(encoding='utf-8'))
    api, web = config['services']['api'], config['services']['web']
    assert api['environment']['ALIPAY_ENABLED'] == '0'
    assert api['environment']['MEMBERSHIP_REMINDERS_ENABLED'] == '0'
    assert not api.get('ports'), 'Backend must not have a public port'
    assert web['ports'] == ['127.0.0.1:8080:8080']
    assert './data:/app/data' in api['volumes']
    assert (ROOT / 'frontend/dist/index.html').is_file(), 'Missing frontend build'
    if (ROOT / 'app/services/poster_service.py').is_file():
        for filename in ('NotoSans-Regular.ttf','NotoSans-Bold.ttf'):
            path = ROOT / 'app/assets/fonts' / filename
            assert path.is_file() and path.read_bytes()[:4] == b'\x00\x01\x00\x00', 'Missing/invalid poster font'
        assert 'SIL Open Font License' in (ROOT / 'app/assets/fonts/OFL.txt').read_text(encoding='utf-8')
    manifest = ROOT / 'bundle-manifest.json'
    if manifest.is_file():
        for relative, expected in json.loads(manifest.read_text(encoding='utf-8')).items():
            path = (ROOT / relative).resolve()
            assert path.is_relative_to(ROOT.resolve()) and path.is_file(), f'Missing bundle file: {relative}'
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, f'File changed: {relative}'
    if args.server:
        assert platform.system() == 'Linux' and platform.machine() == 'x86_64'
        assert shutil.which('docker'), 'Docker is missing'
        assert shutil.disk_usage(ROOT).free >= 8 * 1024**3, 'Need at least 8 GiB free disk'
        assert (ROOT / '.env').is_file(), 'Copy deploy/cloud.env.example to .env first'
    print(json.dumps({'syntax': 'ok', 'configuration': 'ok', 'bundle_integrity': 'ok' if manifest.is_file() else 'not_packaged',
                      'server_checked': args.server, 'models_required': False,
                      'payment_enabled': False, 'network_calls': 0}))


if __name__ == '__main__':
    run()
