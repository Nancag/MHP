#!/usr/bin/env bash
# Run only through the production GitHub Actions workflow. It changes tracked source,
# deliberately preserves /opt/mhp/.env and /opt/mhp/data, then rebuilds both containers.
set -euo pipefail

SITE=/opt/mhp
REF=${MHP_DEPLOY_REF:?MHP_DEPLOY_REF is required}
cd "$SITE"
test -f .env
test -d data
git remote get-url origin | grep -Fx 'https://github.com/Nancag/MHP.git' >/dev/null
git fetch --depth=1 origin "$REF"
git diff --quiet
git diff --cached --quiet
git checkout --detach FETCH_HEAD
python3 deploy/preflight.py --server
docker compose -f compose.json build
docker compose -f compose.json up -d --remove-orphans
curl --fail --silent --show-error http://127.0.0.1:8080/api/health
