#!/usr/bin/env bash
# Daily refresh: collect → aggregate → format → commit/push.
# Lesson learned (luckin-spoilage-dashboard/pipeline/refresh.sh:15): fail fast on any error,
# don't silently emit an empty payload.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${MYSQL_SECRET_NAME:-}" ]]; then
  echo "[refresh] MYSQL_SECRET_NAME is required" >&2
  exit 1
fi

echo "[refresh] $(date -u +%Y-%m-%dT%H:%M:%SZ) — pipeline start"

# 1. Schema probe — best-effort, never blocks the rest of the refresh.
python3 -m pipeline.schema_probe || echo "[refresh] schema probe failed (non-fatal)"

# 2. Collect + aggregate + write data/payload.json.
python3 -m pipeline.frontend_formatter

# 3. Commit if the payload changed. Skip when run in CI without GH credentials.
if [[ "${SKIP_GIT_COMMIT:-0}" != "1" ]]; then
  if ! git diff --quiet data/payload.json; then
    git add data/payload.json
    git commit -m "data: refresh payload $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ "${SKIP_GIT_PUSH:-0}" != "1" ]]; then
      git push
    fi
  else
    echo "[refresh] payload unchanged — nothing to commit"
  fi
fi

echo "[refresh] $(date -u +%Y-%m-%dT%H:%M:%SZ) — done"
