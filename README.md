# Luckin Coffee NA — Store Ops + Efficiency Dashboard

Public, Simplified-Chinese-facing operations dashboard for Luckin Coffee North
America. Reproduces the Modao mockup with a static, network-isolated data
pipeline so the live site on Vercel never touches the internal database.

- **门店看板** (`/`) — filter bar, 9 grouped KPI cards, 19-column store table, donut + pie + TOP10 row, 区间销售明细
- **看板预览** (`/preview`) — 9 KPI cards only (demo / screenshot view)
- **效能看板** (`/efficiency`) — daily timing chart + 区间效能明细 48-row table

```
┌──────────────────────────┐        ┌────────────────────┐        ┌──────────────┐
│ MySQL (internal network) │  →→→   │  pipeline/ (cron)  │  →→→   │ payload.json │
│  luckyus_sales_order …   │        │  SELECT-only       │        │   commit     │
└──────────────────────────┘        └────────────────────┘        └──────┬───────┘
                                                                         ↓
                                                            ┌────────────────────────┐
                                                            │  Vercel (static Next)  │
                                                            │  loads payload at      │
                                                            │  build time, filters   │
                                                            │  + aggregates in the   │
                                                            │  browser. NO API.      │
                                                            └────────────────────────┘
```

## Tech stack

| | |
|---|---|
| Framework      | Next.js 14 (App Router) |
| Language       | TypeScript (`strict: true`, `noUncheckedIndexedAccess: true`) |
| Styling        | Design tokens + CSS Modules |
| Charts         | recharts |
| Export         | SheetJS (`xlsx`) — XLSX + CSV, client-side |
| Pipeline       | Python 3.11, `pymysql`, `boto3` (Secrets Manager) |
| Hosting        | Vercel — no API routes, all data is static |

## Data architecture (non-negotiable)

1. The public site has **no** network path to MySQL. There is exactly one data source: `data/payload.json`.
2. The pipeline is **SELECT-only**, runs inside the internal network, and writes the payload.
3. Credentials are read from AWS Secrets Manager. The secret name is set via `MYSQL_SECRET_NAME` env — never hardcoded.
4. Ratios are stored as `{num, den}` per day per store. The client aggregates as `Σnum / Σden` over any user-selected date range — **never** as the average of daily percentages.
5. Pending sources (QC, labor, ratings, BOM) emit `null` from **the pipeline** and the UI renders "数据源待接入". No fabricated numbers in production.

> **Seed vs pipeline.** The committed `data/payload.json` is a **demo seed** that ships realistic plausible values for *currently-pending* metrics so the deployed UI can be evaluated end-to-end (per the spec's "plausible numbers ... correct numerator/denominator components for ratios"). The production pipeline (`pipeline/frontend_formatter.py`) still emits `null` for unmapped sources. When the live pipeline replaces the seed payload, the UI automatically reverts to "数据源待接入" for any metric whose source remains unmapped.

## Confirmed vs pending sources

| Concept                             | Database.Table                                              | Confidence |
|-------------------------------------|-------------------------------------------------------------|------------|
| Open-store counts                   | `luckyus_iluckyhealth.t_collect_shop_inter`                 | confirmed  |
| Tenant order aggregates             | `luckyus_iluckyhealth.t_collect_order_tenant_inter`         | confirmed  |
| Order facts (channel, pay, status)  | `luckyus_sales_order.t_order`                               | confirmed  |
| Order timing (accept/finish)        | `luckyus_sales_order.t_order_make`                          | confirmed  |
| Order line items (现制 / 外购)       | `luckyus_sales_order.t_order_item`                          | confirmed  |
| Per-store-day totals                | `luckyus_sales_order.t_order_store_fact` (`cycle_type=3`)   | confirmed  |
| Spoilage events                     | `luckyus_scm_shopstock.t_shop_spec_stock_change_record` (`specific_reason_code='015'`) | confirmed (numerator only) |
| Store master                        | `luckyus_opshop.t_shop_info`                                | confirmed  |
| QC audits                           | *to discover* — see `pipeline/schema_probe.py`              | pending    |
| Labor / attendance hours            | *to discover*                                               | pending    |
| Customer rating / 评价               | *to discover*                                               | pending    |
| BOM / theoretical cost              | *to discover*                                               | partial    |

`pipeline/schema_probe.py` searches `information_schema.tables` for likely
matches and writes `pipeline/schema_map.json`. To promote a pending metric to
confirmed:

1. Inspect `schema_map.json` for candidate tables.
2. Add a new collector method in `pipeline/collectors/` that returns
   per-store-per-day rows.
3. Wire those rows into `pipeline/aggregator.py` (set `num` / `den` on the daily
   row).
4. Flip the `source` from `pending` → `confirmed` in **both**
   `lib/metrics.ts` and `pipeline/frontend_formatter.py` (kept in sync by
   convention; the build will surface the change as a code diff).

## Environment variables

| Name                              | Where        | Required | Notes |
|-----------------------------------|--------------|----------|-------|
| `MYSQL_SECRET_NAME`               | pipeline     | ✓        | AWS Secrets Manager secret with `{host,port,user,password,database}`. **No default.** |
| `AWS_REGION`                      | pipeline     | default `us-east-1` | |
| `RETAIN_DAYS`                     | pipeline     | default `90` | per-day rows retained for date range + WoW/MoM (≈1 quarter) |
| `HALF_HOUR_RETAIN_DAYS`           | pipeline     | default `3`  | per-half-hour rows retained for interval tables |
| `LUCKIN_TENANT`                   | pipeline     | default `LKUS` | tenant filter applied to every query |
| `SKIP_GIT_COMMIT` / `SKIP_GIT_PUSH`| pipeline    | optional | for dry runs |
| `NEXT_PUBLIC_EXPORT_REQUIRE_AUTH` | Vercel build | optional | when `true`, the unfiltered full export is gated behind a passphrase |
| `NEXT_PUBLIC_EXPORT_PASSPHRASE`   | Vercel build | optional | passphrase string (no real auth backend) |

## Refresh paths

### A. Docker on an internal host (canonical)

The container runs APScheduler (`pipeline/scheduler/cron_runner.py`), refreshes
the payload daily at 09:00 UTC, and pushes via the GitHub Contents API. No git
push, no self-hosted runner, no per-tick GHA cost.

```bash
cd pipeline
cp .env.example .env                 # fill in MYSQL_SECRET_NAME + GITHUB_TOKEN
docker compose up -d --build
docker compose logs -f pipeline      # watch the first run
```

The container is stateless: `data/payload.json` is regenerated on every tick
and immediately PUT to the repo via REST. Vercel rebuilds on each commit.

### B. Manual `pipeline/refresh.sh` (ad-hoc / dev)

Same code path, but uses `git push` instead of the API and runs once. Useful
for local testing or one-off backfills:

```bash
MYSQL_SECRET_NAME=… bash pipeline/refresh.sh
```

`refresh.sh` is `set -euo pipefail` — empty payloads are never committed.

### C. GitHub Actions (manual fallback)

`.github/workflows/refresh.yml` is left in place but `workflow_dispatch`-only —
its scheduled trigger was removed because the self-hosted runner with MySQL
VPC reach is not currently provisioned. Use it only after wiring a runner.

## Local development

```bash
npm install
python3 seed/seed_payload.py     # writes data/payload.json with realistic seed data
npm run dev                      # http://localhost:3000
```

Quality gates:

```bash
npm run typecheck    # strict TS, must pass with zero errors
npm run lint         # next/eslint, must pass with zero warnings
npm run build        # static export, must succeed
```

## Acceptance verification

Live verifications (run against `npm run dev`):

- `/`, `/preview`, `/efficiency` all render in Chinese; KPI cards show formulas on hover.
- Pending metrics (满意度, QC, labor-based) show "数据源待接入".
- The store table has 19 columns, the first three are frozen, every column is sortable.
- The donut + pie show 自取/外卖 and 现制/外购 shares with % labels.
- The TOP10 table sorts by quantity by default.
- 区间销售明细 and 区间效能明细 render 48 rows each.
- Changing the date range re-aggregates ratios as Σnum/Σden (verify by comparing 2-day vs 7-day windows).
- Filters persist in the URL (`?from=…&to=…&city=…&shop=…`).
- The freshness badge in the header shows the real age of `data/payload.json`.

## Safety notes

- The pipeline asserts read-only via `pipeline/config/settings.py:assert_read_only`. Any SQL that contains a write keyword raises immediately.
- No customer PII is stored in the payload — only aggregated counts, durations, and shop-level metrics.
- All Cost Explorer / S3 / RDS metadata fetched at refresh time is bounded by per-query `LIMIT` clauses.
