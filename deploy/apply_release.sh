#!/bin/sh
set -eu
cd /opt/mhp
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/opt/mhp-backups/pre-release-$stamp
install -d -m 700 "$backup"
docker inspect --format '{{.Image}}' mhp-api-1 > "$backup/api-image"
docker inspect --format '{{.Image}}' mhp-web-1 > "$backup/web-image"
docker compose -f compose.json stop api web
tar --exclude=data/models --exclude=data/.cache --exclude=data/.numba-cache --exclude=data/backups --exclude='*/__pycache__' -czf "$backup/state.tar.gz" app frontend deploy compose.json .env data requirements-cloud.txt requirements-cloud.lock .dockerignore
docker compose -f compose.json start api web
tar -xzf /root/mhp-feature-sync.tar.gz -C /opt/mhp
if ! docker compose -f compose.json build api web > "$backup/build.log" 2>&1; then
    tail -n 55 "$backup/build.log"
    exit 1
fi
docker compose -f compose.json up -d --no-deps api
tries=0
until docker inspect --format '{{.State.Health.Status}}' mhp-api-1 | grep -q '^healthy$'; do
    tries=$((tries+1)); [ "$tries" -lt 60 ] || exit 1
    sleep 3
done
docker compose -f compose.json up -d --no-deps web
docker compose -f compose.json ps -a
curl --fail --silent https://118.178.92.58/api/health
printf '\nRELEASE_BACKUP=%s\n' "$backup"
