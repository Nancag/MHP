"""Publish an allowlisted static download update; never restart or alter the API."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ENTRY = '''<!-- MHP_DOWNLOAD_ENTRY_START -->
<link rel="stylesheet" href="/download-entry.css">
<a id="mhp-download-entry" href="/download.html" hidden>Windows 客户端下载</a>
<script defer src="/download-entry.js"></script>
<!-- MHP_DOWNLOAD_ENTRY_END -->'''


def run(arguments, allow_missing=False):
    result = subprocess.run(arguments, capture_output=True)
    if result.returncode and not allow_missing:
        raise RuntimeError('Command failed: ' + ' '.join(arguments[:3]))
    return result


def safe(root, relative):
    target = root / relative
    if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
        raise ValueError('Unsafe target: ' + relative)
    return target


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.mhp-download-tmp')
    if temporary.exists() or temporary.is_symlink():
        raise ValueError('Temporary file already exists')
    temporary.write_bytes(data)
    temporary.chmod(0o644)
    temporary.replace(path)


def patched_index(data):
    text = data.decode('utf-8')
    # New frontend versions already contain Vue links; this old-build entry hides itself.
    if 'MHP_DOWNLOAD_ENTRY_START' in text:
        text, count = re.subn(r'<!-- MHP_DOWNLOAD_ENTRY_START -->.*?<!-- MHP_DOWNLOAD_ENTRY_END -->', ENTRY, text, flags=re.S)
        if count != 1:
            raise ValueError('Unexpected duplicate download entries')
    else:
        if text.count('</body>') != 1:
            raise ValueError('Unexpected homepage HTML')
        text = text.replace('</body>', ENTRY + '\n</body>')
    return text.encode('utf-8')


def restore(root, container, backup):
    journal = json.loads((backup / 'journal.json').read_text())
    for name, existed in reversed(list(journal['host'].items())):
        target = safe(root, name)
        if existed:
            write(target, (backup / 'host' / name).read_bytes())
        elif target.exists():
            target.unlink()
    for name, existed in journal['remote'].items():
        if existed:
            run(['docker', 'cp', str(backup / 'remote' / name), f'{container}:/srv/mhp/{name}'])
        else:
            run(['docker', 'exec', container, 'rm', '-f', '/srv/mhp/' + name])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/opt/mhp'))
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('Run as root on the Linux server')
    compose = safe(root, 'compose.json')
    if not compose.is_file():
        raise ValueError('Existing compose.json not found')
    container = run(['docker', 'compose', '-f', str(compose), 'ps', '-q', 'web']).stdout.decode().strip()
    if not re.fullmatch(r'[a-f0-9]{12,64}', container):
        raise ValueError('Expected exactly one running web container')
    if args.rollback:
        backup = args.rollback.resolve(strict=True)
        if not backup.is_relative_to(safe(root, 'data/backups').resolve()):
            raise ValueError('Rollback directory must be inside project backups')
        restore(root, container, backup)
        print('DOWNLOAD_ROLLBACK_OK')
        return
    bundle = Path(__file__).resolve().parent
    release = json.loads((bundle / 'release.json').read_text(encoding='utf-8'))
    version = release['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Unexpected version')
    names = {'download.html', 'download-entry.js', 'download-entry.css', 'downloads/windows/README.txt',
             'downloads/windows/SHA256SUMS', f'downloads/windows/MHP-Setup-{version}-x64.exe',
             f'downloads/windows/MHP-{version}-x64-portable.zip'}
    if 'client-release.json' in release['files']:names.add('client-release.json')
    if set(release['files']) != names:
        raise ValueError('Unexpected public files')
    files = {}
    for name, expected in release['files'].items():
        data = safe(bundle, 'public/' + name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Public file checksum failed: ' + name)
        files[name] = data
    host_index = safe(root, 'frontend/dist/index.html')
    cloud_index = run(['docker', 'exec', container, 'cat', '/srv/mhp/index.html']).stdout
    if host_index.read_bytes() != cloud_index:
        raise ValueError('Cloud and host homepage differ; no files were changed')
    for path in ['/srv/mhp', '/srv/mhp/index.html', '/srv/mhp/downloads', '/srv/mhp/downloads/windows']:
        run(['docker', 'exec', container, 'test', '!', '-L', path])
    for prefix in ['frontend/public/', 'frontend/dist/']:
        for name in names:
            safe(root, prefix + name)
    index = patched_index(cloud_index)
    print(json.dumps({'version': version, 'public_files': len(files), 'web_container': container[:12], 'api_restart': False}))
    if args.check:
        print('DOWNLOAD_PREFLIGHT_OK')
        return
    backups = safe(root, 'data/backups')
    backups.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='download-site-', dir=backups))
    journal = {'host': {}, 'remote': {}, 'web_container': container}
    targets = {prefix + name: data for prefix in ['frontend/public/', 'frontend/dist/'] for name, data in files.items()}
    targets['frontend/dist/index.html'] = index
    # Capture every previous file before any published file is changed.
    for name in targets:
        source = safe(root, name)
        journal['host'][name] = source.is_file()
        if source.is_file():
            target = backup / 'host' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for name in list(files) + ['index.html']:
        exists = run(['docker', 'exec', container, 'test', '-f', '/srv/mhp/' + name], allow_missing=True)
        if exists.returncode not in (0, 1):
            raise RuntimeError('Could not inspect existing website files')
        journal['remote'][name] = exists.returncode == 0
        if exists.returncode == 0:
            destination = backup / 'remote' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            run(['docker', 'cp', f'{container}:/srv/mhp/{name}', str(destination)])
    (backup / 'journal.json').write_text(json.dumps(journal, indent=2), encoding='utf-8')
    try:
        for name, data in targets.items():
            write(safe(root, name), data)
        run(['docker', 'exec', container, 'mkdir', '-p', '/srv/mhp/downloads/windows'])
        for name in list(files) + ['index.html']:
            run(['docker', 'cp', str(safe(root, 'frontend/dist/' + name)), f'{container}:/srv/mhp/{name}'])
        for name, data in {**files, 'index.html': index}.items():
            observed = run(['docker', 'exec', container, 'sha256sum', '/srv/mhp/' + name]).stdout.decode().split()[0]
            if observed != hashlib.sha256(data).hexdigest():
                raise ValueError('Published checksum failed: ' + name)
    except Exception:
        restore(root, container, backup)
        raise
    print('DOWNLOAD_PUBLISH_OK')
    print('Backup: ' + str(backup))
    print('https://118.178.92.58/download.html')


if __name__ == '__main__':
    main()
