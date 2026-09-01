#!/usr/bin/env bash
# Redeploy the collection container on the internal host.
#
# The container is only rebuilt by hand, so merged code sits inert until
# someone runs this. Its sibling (luckin-ops-dashboard) went 11 days and 108
# published snapshots on stale code before anyone noticed, which is why the
# payload now records how it was collected: after this runs, check
# meta.collection_mode in data/payload.json — an older payload has no such key
# at all, so its absence means the container is still on pre-2026-09-01 code.
#
# The compose project name is pinned in docker-compose.yml, so this cannot tear
# down the sibling pipelines that also live in a `pipeline/` directory.

set -euo pipefail

cd "$(dirname "$0")"

git pull

docker compose down

docker builder prune -f

docker compose build --no-cache

docker compose up -d

docker compose logs -f
