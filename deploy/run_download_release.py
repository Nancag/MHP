"""Verified one-shot server rollout from an explicitly hashed download archive."""
import ast
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def main():
    expected = sys.argv[1]
    archive = Path('/root/mhp-download-release.tar.gz')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('Uploaded archive checksum mismatch')
    work = Path(tempfile.mkdtemp(prefix='mhp-download-publish-', dir='/root'))
    with tarfile.open(archive, 'r:gz') as stream:
        for member in stream.getmembers():
            target = work / member.name
            if not member.isfile() or not target.resolve().is_relative_to(work.resolve()):
                raise ValueError('Unexpected archive entry')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(stream.extractfile(member).read())
    publisher = work / 'publish_downloads.py'
    ast.parse(publisher.read_text(encoding='utf-8'), filename=str(publisher))
    subprocess.run(['python3', '-B', str(publisher), '--check'], check=True)
    subprocess.run(['python3', '-B', str(publisher)], check=True)
    # Build an updated web image so a later container recreation keeps the files.
    # Use a minimal context: no .env, user records, models or API source.
    root = Path('/opt/mhp')
    image_context = work / 'web-image-context'
    (image_context / 'deploy').mkdir(parents=True)
    for name in ['Dockerfile.web', 'Caddyfile']:
        shutil.copy2(root / 'deploy' / name, image_context / 'deploy' / name)
    shutil.copytree(root / 'frontend/dist', image_context / 'frontend/dist')
    previous = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', 'mhp-web'], text=True).strip()
    subprocess.run(['docker', 'build', '--pull=false', '--network=none', '-t', 'mhp-web',
                    '-f', str(image_context / 'deploy/Dockerfile.web'), str(image_context)], check=True)
    current = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', 'mhp-web'], text=True).strip()
    report = {'archive_sha256': expected, 'previous_web_image': previous, 'new_web_image': current,
              'api_restarted': False, 'web_restarted': False, 'download_page': 'https://118.178.92.58/download.html'}
    (work / 'publish-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('DOWNLOAD_RELEASE_DURABLE_OK')


if __name__ == '__main__':
    main()
