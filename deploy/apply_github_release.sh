#!/usr/bin/env bash
# Execute only on the production host. It preserves production configuration and user data.
set -euo pipefail

SITE=${MHP_DEPLOY_PATH:-/opt/mhp}
SHA=${MHP_RELEASE_SHA:?MHP_RELEASE_SHA is required}
ARCHIVE=/tmp/mhp-release-${SHA}.tar.gz
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/opt/mhp-backups/github-release-${STAMP}
STAGE=$(mktemp -d /opt/mhp-release.XXXXXX)
ROLLBACK_API="mhp-api:rollback-${STAMP}"
ROLLBACK_WEB="mhp-web:rollback-${STAMP}"

cleanup() { rm -rf "$STAGE" "$ARCHIVE"; }
trap cleanup EXIT
test "$SITE" = /opt/mhp
test -d "$SITE/data"
test -f "$SITE/.env"
test -f "$SITE/compose.json"
test -f "$ARCHIVE"
test "$(sha256sum "$ARCHIVE" | awk '{print $1}')" = "$SHA"

python3 - "$ARCHIVE" "$STAGE" <<'PY'
import hashlib, json, sys, tarfile
from pathlib import Path
archive, root = map(Path, sys.argv[1:])
with tarfile.open(archive, 'r:gz') as stream:
    members = stream.getmembers()
    for item in members:
        target = (root / item.name).resolve()
        if not item.isfile() or not target.is_relative_to(root.resolve()):
            raise SystemExit('unsafe release archive')
    stream.extractall(root, filter='data')
manifest = json.loads((root / 'release-manifest.json').read_text())
for relative, expected in manifest.items():
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise SystemExit('missing release input: ' + relative)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected: raise SystemExit('release checksum mismatch: ' + relative)
if not (root / 'frontend/dist/index.html').is_file(): raise SystemExit('missing built frontend')
PY

install -d -m 700 "$BACKUP"
tar -C "$SITE" -czf "$BACKUP/source.tar.gz" app extensions deploy frontend requirements-cloud.txt requirements-cloud.lock .dockerignore
cp -a "$SITE/compose.json" "$BACKUP/compose.json"
docker image inspect mhp-api >/dev/null && docker tag mhp-api "$ROLLBACK_API"
docker image inspect mhp-web >/dev/null && docker tag mhp-web "$ROLLBACK_WEB"

# Client binaries are not part of the source archive. Keep them until separately published.
if test -d "$SITE/frontend/dist/downloads"; then
    cp -a "$SITE/frontend/dist/downloads" "$BACKUP/downloads"
fi

restore() {
    tar -C "$SITE" -xzf "$BACKUP/source.tar.gz"
    cp -a "$BACKUP/compose.json" "$SITE/compose.json"
    rm -rf "$SITE/frontend/dist/downloads"
    test -d "$BACKUP/downloads" && cp -a "$BACKUP/downloads" "$SITE/frontend/dist/downloads"
    docker tag "$ROLLBACK_API" mhp-api 2>/dev/null || true
    docker tag "$ROLLBACK_WEB" mhp-web 2>/dev/null || true
    docker compose -f "$SITE/compose.json" up -d api web || true
}

if ! (
    rm -rf "$SITE/app" "$SITE/extensions" "$SITE/deploy" "$SITE/frontend"
    cp -a "$STAGE/app" "$STAGE/extensions" "$STAGE/deploy" "$STAGE/frontend" "$SITE/"
    cp -a "$STAGE/requirements-cloud.txt" "$STAGE/requirements-cloud.lock" "$STAGE/.dockerignore" "$SITE/"
    test -d "$BACKUP/downloads" && cp -a "$BACKUP/downloads" "$SITE/frontend/dist/downloads" || true
    docker compose -f "$SITE/compose.json" config --quiet
    docker compose -f "$SITE/compose.json" build api web
    docker compose -f "$SITE/compose.json" up -d api web
    for _ in $(seq 1 60); do
        curl --fail --silent --show-error http://127.0.0.1:8080/api/health && exit 0
        sleep 3
    done
    exit 1
); then
    restore
    echo "RELEASE_ROLLED_BACK=$BACKUP" >&2
    exit 1
fi
