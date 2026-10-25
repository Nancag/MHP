"""Validate release packages, stage public files and create a static-only update."""
import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'data/windows-client/release'
PUBLIC = ROOT / 'frontend/public'
STAGE = ROOT / 'data/windows-client/website-release'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((RELEASE / 'build-manifest.json').read_text(encoding='utf-8'))
    version = manifest['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Unexpected version')
    installer = f'MHP-Setup-{version}-x64.exe'
    portable = f'MHP-{version}-x64-portable.zip'
    packages = [installer, portable]
    replacements = {'VERSION': version}
    sums = []
    for label, name in zip(['INSTALLER', 'PORTABLE'], packages):
        source = RELEASE / name
        record = manifest['packages'][name]
        if source.stat().st_size != record['bytes'] or digest(source) != record['sha256']:
            raise ValueError(f'Package verification failed: {name}')
        replacements.update({label: name, label + '_SIZE': f"{record['bytes'] / 1048576:.2f} MB", label + '_SHA': record['sha256']})
        sums.append(f"{record['sha256']}  {name}\n")
    if (RELEASE / 'SHA256SUMS').read_text(encoding='utf-8') != ''.join(sums):
        raise ValueError('SHA256SUMS differs from build manifest')
    html = (ROOT / 'desktop/windows/download.html').read_text(encoding='utf-8')
    for name, value in replacements.items():
        html = html.replace('{{' + name + '}}', value)
    if '{{' in html:
        raise ValueError('Unresolved download page placeholders')
    contents = {'download.html': html.encode(),'client-release.json':(RELEASE/'client-release.json').read_bytes()}
    for name in ['download-entry.css', 'download-entry.js']:
        contents[name] = (ROOT / 'desktop/windows' / name).read_bytes()
    for name in packages + ['README.txt', 'SHA256SUMS']:
        contents['downloads/windows/' + name] = (RELEASE / name).read_bytes()
    for folder in [PUBLIC, ROOT / 'frontend/dist', STAGE / 'public']:
        for name, data in contents.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        managed=folder/'downloads/windows'
        for old in managed.iterdir():
            if old.name not in packages and re.fullmatch(r'MHP-(?:Setup-)?\d+\.\d+\.\d+-x64(?:-portable)?\.(?:exe|zip)',old.name) and old.is_file() and not old.is_symlink():old.unlink()
    records = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    (STAGE / 'release.json').write_text(json.dumps({'version': version, 'files': records}, indent=2) + '\n', encoding='utf-8')
    shutil.copy2(ROOT / 'deploy/publish_downloads.py', STAGE / 'publish_downloads.py')
    output = ROOT / 'data/cloud-upload/mhp-download-release.tar.gz'
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, 'w:gz') as archive:
        for name in ['release.json', 'publish_downloads.py']:
            archive.add(STAGE / name, arcname=name)
        for name in records:
            archive.add(STAGE / 'public' / name, arcname='public/' + name)
    output.with_name('mhp-download-release.sha256').write_text(f'{digest(output)}  {output.name}\n', encoding='utf-8')
    print(json.dumps({'archive': str(output), 'bytes': output.stat().st_size, 'sha256': digest(output), 'public_files': len(records)}))


if __name__ == '__main__':
    main()
