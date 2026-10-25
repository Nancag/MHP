"""Create allowlisted upload archives; never include credentials or user data."""
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/cloud-upload'


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = list((ROOT / 'app').rglob('*.py'))
    files += [ROOT/'extensions/mhp-collector'/name for name in ('manifest.json','popup.html','popup.css','popup.js','extractor.js','bridge.js','background.js','README.md','MHP-Collector-Setup.exe','installer-build.json')]
    files += [ROOT / 'app/assets/fonts' / name for name in ('NotoSans-Regular.ttf','NotoSans-Bold.ttf','OFL.txt','README.md')]
    files += [p for p in (ROOT / 'frontend/dist').rglob('*') if p.is_file()]
    files += [ROOT / p for p in ('requirements-cloud.txt', 'requirements-cloud.lock', 'compose.json', '.dockerignore',
                                 'deploy/Dockerfile.api', 'deploy/Dockerfile.web', 'deploy/Caddyfile',
                                 'deploy/preflight.py', 'deploy/cloud.env.example',
                                 'deploy/publish_downloads.py', 'deploy/backup_worker.py',
                                 'deploy/README.zh-CN.md')]
    for path in files:
        assert path.is_file() and path.name != '.env' and path.suffix not in ('.pem', '.key', '.db')
        assert not path.is_relative_to(ROOT / 'data') and not path.is_relative_to(ROOT / 'private')
    for script in (ROOT / 'frontend/dist').rglob('*.js'):
        text = script.read_text(encoding='utf-8')
        assert 'http://127.0.0.1:8000' not in text and 'http://localhost:8000' not in text, 'Production API points to local development server'
    manifest = {p.relative_to(ROOT).as_posix(): digest_file(p) for p in sorted(set(files))}
    code = OUTPUT / 'mhp-cloud-code.tar.gz'
    with tarfile.open(code, 'w:gz', compresslevel=6) as archive:
        for path in sorted(set(files)):
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
        contents = json.dumps(manifest, indent=2).encode()
        item = tarfile.TarInfo('bundle-manifest.json')
        item.size = len(contents)
        item.mode = 0o644
        archive.addfile(item, io.BytesIO(contents))
    with tempfile.TemporaryDirectory(dir=OUTPUT) as directory:
        extracted = Path(directory)
        with tarfile.open(code, 'r:gz') as archive:
            archive.extractall(extracted, filter='data')
        subprocess.run([sys.executable, '-B', str(extracted / 'deploy/preflight.py')], cwd=extracted, check=True)
    outputs = [code]
    # Write LF bytes explicitly: Windows text mode would append CR to Linux filenames.
    (OUTPUT / 'SHA256SUMS').write_bytes(''.join(f'{digest_file(p)}  {p.name}\n' for p in outputs).encode('ascii'))
    result = {'archives': [{'name': p.name, 'size_bytes': p.stat().st_size} for p in outputs],
              'code_files': len(manifest), 'archive_integrity_verified': True,
              'secrets_included': False, 'user_database_included': False}
    (OUTPUT / 'bundle-report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    run()
