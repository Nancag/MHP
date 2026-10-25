#!/bin/sh
set -eu
python3 /usr/local/lib/mhp/backup_worker.py --scheduled
cd /opt/mhp
tar -xzf /root/mhp-feature-sync.tar.gz -C /opt/mhp
DOCKER_BUILDKIT=0 docker build -f deploy/Dockerfile.web -t mhp-web:latest . > /root/mhp-web-release.log 2>&1
sh /root/build_cached.sh
python3 - <<'PY'
from pathlib import Path
import re
root=Path('/opt/mhp/frontend/dist/downloads/windows').resolve()
for path in root.iterdir():
    if path.is_symlink() or not path.resolve().is_relative_to(root):continue
    match=re.fullmatch(r'MHP-(?:Setup-)?(\d+\.\d+\.\d+)-x64(?:-portable)?\.(?:exe|zip)',path.name)
    if match and tuple(map(int,match[1].split('.')))<(1,0,0) and path.is_file():path.unlink()
PY
python3 /usr/local/lib/mhp/backup_worker.py --scheduled
curl --fail --silent https://118.178.92.58/api/health
printf '\nRELEASE_100_COMPLETE\n'
