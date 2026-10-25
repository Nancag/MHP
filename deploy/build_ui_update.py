"""Package a frontend update against the original deployment manifest, preserving data and models."""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/cloud-upload'


def run():
    base = OUTPUT / 'mhp-cloud-code.tar.gz'
    with tarfile.open(base, 'r:gz') as archive:
        manifest = json.load(archive.extractfile('bundle-manifest.json'))
    manifest = {name: value for name, value in manifest.items() if not name.startswith('frontend/dist/')}
    files = sorted(p for p in (ROOT / 'frontend/dist').rglob('*') if p.is_file())
    for path in files:
        manifest[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    output = OUTPUT / 'mhp-ui-update.tar.gz'
    with tarfile.open(output, 'w:gz', compresslevel=6) as archive:
        for path in files:
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
        contents = json.dumps(manifest, indent=2).encode()
        item = tarfile.TarInfo('bundle-manifest.json')
        item.size, item.mode = len(contents), 0o644
        archive.addfile(item, io.BytesIO(contents))
    # Verify the actual base+update combination before giving the archive to the user.
    with tempfile.TemporaryDirectory(dir=OUTPUT) as directory:
        extracted = Path(directory)
        for package in (base, output):
            with tarfile.open(package, 'r:gz') as archive:
                archive.extractall(extracted, filter='data')
        subprocess.run([sys.executable, '-B', str(extracted / 'deploy/preflight.py')], cwd=extracted, check=True)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (OUTPUT / 'mhp-ui-update.sha256').write_bytes(f'{digest}  {output.name}\n'.encode('ascii'))
    print(json.dumps({'archive': str(output), 'size_bytes': output.stat().st_size,
                      'base_archive_unchanged': True, 'merged_manifest_verified': True,
                      'secrets_or_database_included': False}))


if __name__ == '__main__':
    run()
