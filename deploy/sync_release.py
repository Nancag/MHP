"""Build a code-only release; deployment configuration and all private data stay remote."""
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def build(label='feature-sync'):
    output=ROOT/'data/cloud-upload'/f'mhp-{label}.tar.gz'
    output.parent.mkdir(parents=True,exist_ok=True)
    files=list((ROOT/'app').rglob('*.py'))+list((ROOT/'app/assets/fonts').glob('*'))
    files += [p for p in (ROOT/'frontend/dist').rglob('*') if p.is_file()]
    files += [ROOT/'extensions/mhp-collector'/name for name in ('manifest.json','popup.html','popup.css','popup.js','extractor.js','bridge.js','background.js','README.md')]
    files += [ROOT/p for p in ('requirements-cloud.txt','requirements-cloud.lock','.dockerignore','deploy/Dockerfile.api','deploy/Dockerfile.web','deploy/Caddyfile','deploy/preflight.py','deploy/publish_downloads.py','deploy/backup_worker.py')]
    with tarfile.open(output,'w:gz') as archive:
        for p in sorted(set(files)):
            if p.is_file():archive.add(p,arcname=p.relative_to(ROOT).as_posix(),recursive=False)
    print(json.dumps({'file':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size}))
    return output
if __name__=='__main__':build()
