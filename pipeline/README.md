# `pipeline/` — refresh `data/payload.json`

The pipeline runs inside the internal network, queries MySQL read-only, and
writes a single static JSON payload that the public Next.js client consumes.
The public site never touches a database.

## Files

| File                         | Purpose |
|------------------------------|---------|
| `config/settings.py`         | AWS Secrets Manager loader. `MYSQL_SECRET_NAME` is required — no default. Includes `assert_read_only` SQL safety check. |
| `collectors/stores.py`       | Store directory + `operating_today` (any completed order in last 24h ET). |
| `collectors/orders.py`       | Per-day per-store order/product counts, SPU quantities. |
| `collectors/efficiency.py`   | Per-half-hour efficiency timings + per-half-hour sales (channel + category split). |
| `collectors/spoilage.py`     | Spoilage events (reason `015`). Numerator only — theoretical denominator pending. |
| `collectors/health.py`       | `t_collect_*_inter` cross-check (non-blocking). |
| `aggregator.py`              | Joins collectors into per-store-day rows + half-hour rollups. |
| `frontend_formatter.py`      | Writes `data/payload.json` matching `lib/types.ts`. |
| `schema_probe.py`            | Discovers candidate tables for QC / labor / rating / BOM. Writes `pipeline/schema_map.json`. |
| `refresh.sh`                 | Chains probe → format → git commit. `set -euo pipefail`. |

## Running it

```bash
MYSQL_SECRET_NAME=collector/mysql AWS_REGION=us-east-1 \
  bash pipeline/refresh.sh
```

Dry run (no commit, no push):

```bash
MYSQL_SECRET_NAME=collector/mysql SKIP_GIT_COMMIT=1 SKIP_GIT_PUSH=1 \
  python3 -m pipeline.frontend_formatter
```

Schema probe only:

```bash
MYSQL_SECRET_NAME=collector/mysql python3 -m pipeline.schema_probe
cat pipeline/schema_map.json | jq '.qc_audit.matches | length'
```

## Tenant / timezone

All queries filter `WHERE tenant = 'LKUS'` and bucket timestamps to ET via
`CONVERT_TZ(col, 'UTC', 'US/Eastern')` (DST-aware in MySQL).

## Safety

- SELECT-only — `assert_read_only` rejects any SQL with a write keyword.
- No hardcoded credentials — every connection goes through Secrets Manager.
- `refresh.sh` is fail-fast (`set -euo pipefail`); a half-collected payload never lands in `data/`.
