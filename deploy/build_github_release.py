"""Build a code-only production archive after the GitHub runner builds Vue."""
import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'github-release'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    dist = ROOT / 'frontend' / 'dist'
    if not (dist / 'index.html').is_file():
        raise ValueError('frontend/dist/index.html is missing; run npm ci and npm run build first')
    files = list((ROOT / 'app').rglob('*.py'))
    files += list((ROOT / 'app' / 'assets' / 'fonts').glob('*'))
    files += list((ROOT / 'app' / 'assets' / 'templates').glob('*'))
    files += [path for path in dist.rglob('*') if path.is_file()]
    files += [ROOT / 'extensions' / 'mhp-collector' / name for name in
              ('manifest.json','popup.html','popup.css','popup.js','extractor.js','bridge.js','background.js','README.md','MHP-Collector-Setup.exe','installer-build.json')]
    files += [ROOT / name for name in ('requirements-cloud.txt','requirements-cloud.lock','.dockerignore')]
    files += [path for path in (ROOT / 'deploy').glob('*') if path.is_file()]
    clean = []
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError('missing or unsafe release input: ' + str(path))
        relative = path.relative_to(ROOT)
        if relative.parts[0] in ('data','private') or path.name == '.env' or path.suffix in ('.pem','.key','.pfx','.db'):
            raise ValueError('private input rejected: ' + str(relative))
        clean.append(path)
    manifest = {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(set(clean))}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    archive = OUTPUT / 'mhp-release.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=6) as stream:
        for path in sorted(set(clean)):
            stream.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
        data = json.dumps(manifest, sort_keys=True, indent=2).encode()
        info = tarfile.TarInfo('release-manifest.json'); info.size = len(data); info.mode = 0o644
        stream.addfile(info, io.BytesIO(data))
    report = {'archive': str(archive), 'sha256': digest(archive), 'files': len(manifest)}
    (OUTPUT / 'release-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
