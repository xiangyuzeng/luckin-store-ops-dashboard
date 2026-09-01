# `pipeline/` — refresh `data/payload.json`

The pipeline runs inside the internal network, queries MySQL read-only, and
writes a single static JSON payload that the public Next.js client consumes.
The public site never touches a database.

## Files

| File                         | Purpose |
|------------------------------|---------|
| `config/settings.py`         | AWS Secrets Manager loader. `MYSQL_SECRET_NAME` is required — no default. Includes `assert_read_only` SQL safety check. |
| `collectors/stores.py`       | Store directory + `operating_today` (any completed order in last 24h ET). |
| `collectors/orders.py`       | Per-day per-store order/product counts, SPU quantities (one scan for `spu_name` + `spu_code`). |
| `collectors/efficiency.py`   | Per-half-hour efficiency timings + per-half-hour sales (channel + category split). |
| `collectors/spoilage.py`     | Spoilage events (reason `015`). Numerator only — theoretical denominator pending. Returns rows keyed by `shop_dept_id`; translate to `shop_no` via `t_shop_info.dept_id` when wiring the BOM denominator. |
| `aggregator.py`              | Joins collectors into per-store-day rows + half-hour rollups. |
| `frontend_formatter.py`      | Writes `data/payload.json` matching `lib/types.ts`. |
| `schema_probe.py`            | Discovers candidate tables for QC / labor / rating / BOM. Writes `pipeline/schema_map.json`. |
| `refresh.sh`                 | Chains probe → format → git commit. `set -euo pipefail`. |

## Collection window

Each run re-queries only the last `INCREMENTAL_DAYS` (3) ET days and splices
them into the previous `data/payload.json`; days older than that are copied
forward. On `FULL_REBUILD_WEEKDAY` (Sunday), and whenever there is no usable
previous payload, it queries the full `RETAIN_DAYS` (90) instead. Set
`FORCE_FULL_REBUILD=1` for a one-off rebuild — after an outage, or after
changing how a metric is computed.

Why: a 90-day predicate covers nearly all of `t_order` (1.34M rows), so the
optimizer drops `idx_pay_time` and full-scans. The 2026-09-01 L0 slow-query
audit (`LCNA-DBA-SQL-2026-0901-B`) measured this pipeline at 366.5 s of DB time
over 7 days — the largest single group in that batch — against 0.15 s for the
same query shape over 3 days. `meta.collection_mode` and `meta.collected_from`
in the payload say which days a given run actually measured.

The SPU collector returns `spu_code` and `spu_name` in one scan;
`aggregate_spu_rows()` projects it onto whichever column a consumer needs.
Those were two queries scanning the same 2.09M rows twice a night.

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
