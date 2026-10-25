#!/bin/sh
set -eu
cd /opt/mhp
# Full rebuild prevents retired ML packages and old cutout routes surviving in a cached runtime image.
docker compose -f compose.json build api web
docker compose -f compose.json up -d api web
curl --fail --silent https://118.178.92.58/api/health
