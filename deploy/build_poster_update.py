"""Build a code+fonts+UI update without replacing the original code/model archives."""
import hashlib
import argparse
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/cloud-upload'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',choices=('poster','reference-set','material'),default='poster')
    name=parser.parse_args().name
    base = OUTPUT/'mhp-cloud-code.tar.gz'
    before = digest(base)
    with tarfile.open(base,'r:gz') as archive:
        manifest = json.load(archive.extractfile('bundle-manifest.json'))
    manifest = {k:v for k,v in manifest.items() if not k.startswith(('app/','tests/','frontend/dist/'))}
    files = list((ROOT/'app').rglob('*.py'))
    files += [p for p in (ROOT/'frontend/dist').rglob('*') if p.is_file()]
    files += [ROOT/'app/assets/fonts'/name for name in ('NotoSans-Regular.ttf','NotoSans-Bold.ttf','OFL.txt','README.md')]
    files += [ROOT/'deploy/preflight.py',ROOT/'deploy/build_bundle.py',ROOT/'deploy/cloud.env.example',ROOT/'docs/ptmd-quality-target.md',ROOT/'docs/ptmd-reference-sets.md']
    files += [ROOT/'extensions/mhp-collector'/part for part in ('manifest.json','popup.html','popup.css','popup.js','extractor.js','bridge.js','background.js','README.md')]
    files += [ROOT/part for part in ('.dockerignore','deploy/Dockerfile.api','deploy/publish_downloads.py','deploy/backup_worker.py')]
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        assert not path.is_relative_to(ROOT/'data') and path.suffix not in ('.db','.key','.pem') and path.name!='.env'
        manifest[relative]=digest(path)
    package = OUTPUT/f'mhp-{name}-update.tar.gz'
    with tarfile.open(package,'w:gz',compresslevel=6) as archive:
        for path in sorted(set(files)):
            archive.add(path,arcname=path.relative_to(ROOT).as_posix(),recursive=False)
        contents=json.dumps(manifest,indent=2).encode()
        item=tarfile.TarInfo('bundle-manifest.json')
        item.size,item.mode=len(contents),0o644
        archive.addfile(item,io.BytesIO(contents))
    with tempfile.TemporaryDirectory(dir=OUTPUT) as directory:
        extracted=Path(directory)
        for part in (base,package):
            with tarfile.open(part,'r:gz') as archive:
                archive.extractall(extracted,filter='data')
        subprocess.run([sys.executable,'-B',str(extracted/'deploy/preflight.py')],cwd=extracted,check=True)
    assert digest(base)==before, 'Original upload archive changed'
    (OUTPUT/f'mhp-{name}-update.sha256').write_bytes(f'{digest(package)}  {package.name}\n'.encode('ascii'))
    print(json.dumps({'archive':str(package),'size_bytes':package.stat().st_size,'merged_manifest_verified':True,
                      'base_archive_unchanged':True,'secrets_or_user_database_included':False}))


if __name__=='__main__':
    run()
