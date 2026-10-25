#!/bin/sh
set -eu
sh /root/install_operations.sh
python3 /usr/local/lib/mhp/backup_worker.py --scheduled
cd /opt/mhp
python3 /root/configure_workspace.py
tar -xzf /root/mhp-feature-sync.tar.gz -C /opt/mhp
DOCKER_BUILDKIT=0 docker build -f deploy/Dockerfile.web -t mhp-web:latest . > /root/mhp-web-release.log 2>&1
sh /root/build_cached.sh
systemctl start mhp-operations.service
python3 /usr/local/lib/mhp/backup_worker.py --scheduled
curl --fail --silent https://118.178.92.58/api/health
printf '\nWORKSPACE_RELEASE_COMPLETE\n'
