"""End-to-end pipeline: read DB → aggregate → write data/payload.json.

Run:
    MYSQL_SECRET_NAME=<your-secret> python3 -m pipeline.frontend_formatter

The script writes `data/payload.json` at the repo root and is idempotent.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .aggregator import (
    build_daily_store_rows,
    normalize_half_hour_efficiency,
    normalize_half_hour_sales,
    normalize_spu_daily,
    rollup_durations_into_daily,
)
from .collectors.efficiency import fetch_half_hour_efficiency, fetch_half_hour_sales
from .collectors.health import fetch_open_store_counts, fetch_tenant_order_counters
from .collectors.orders import (
    fetch_daily_orders,
    fetch_daily_products,
    fetch_spu_daily,
    fetch_store_day_facts,
)
from .collectors.spoilage import fetch_daily_spoilage
from .collectors.stores import fetch_store_directory

RETAIN_DAYS = int(os.environ.get("RETAIN_DAYS", "40"))
HALF_HOUR_RETAIN_DAYS = int(os.environ.get("HALF_HOUR_RETAIN_DAYS", "3"))
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "payload.json"
TENANT = os.environ.get("LUCKIN_TENANT", "LKUS")

# Mirrors lib/metrics.ts. The pipeline DOES NOT compute pending metrics — it just
# declares the registry so the client always sees a consistent set.
METRICS: list[dict[str, Any]] = [
    {"key": "orderCount",         "label_zh": "订单数量",           "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "已完成订单数 (t_order.status=已完成)"},
    {"key": "productCount",       "label_zh": "商品数量",           "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "已完成订单的商品数 (t_order_item ⋈ t_order)"},
    {"key": "satisfaction",       "label_zh": "满意度",             "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "pending",   "formula_zh": "1 − 不满意订单数 / 订单数"},
    {"key": "hourlyCups",         "label_zh": "小时杯量",           "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "pending",   "formula_zh": "等效商品数 / 总工时"},
    {"key": "perfHourlyCups",     "label_zh": "绩效小时杯量",       "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "pending",   "formula_zh": "等效商品数 / (考勤工时 − 会议 − 培训 − 帮带训)"},
    {"key": "hourlyCupAchieve",   "label_zh": "小时杯量达成比",     "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "pending",   "formula_zh": "(绩效小时杯量 / 理论小时杯量) × 100%"},
    {"key": "qcPassRate",         "label_zh": "品控稽核达标率",     "format": "percent",  "comparisons": ["sequential"],   "good_direction": "up",   "source": "pending",   "formula_zh": "≥80分稽核任务数 / 稽核任务数"},
    {"key": "qcAvgScore",         "label_zh": "品控稽核平均分",     "format": "score",    "comparisons": ["sequential"],   "good_direction": "up",   "source": "pending",   "formula_zh": "稽核总分 / 稽核任务数"},
    {"key": "materialLossRate",   "label_zh": "原料损耗率",         "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "down", "source": "partial",   "formula_zh": "(实际 − 理论消耗成本) / 理论消耗成本"},
    {"key": "avgDailyProducts",   "label_zh": "单店日均商品数",     "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_store_fact 商品数 / 运营天数"},
    {"key": "avgDailyFreshMade",  "label_zh": "单店日均现制商品数", "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_item 现制类目计数 / 运营天数"},
    {"key": "avgDailyEquiv",      "label_zh": "单店日均等效商品数", "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "(现制 + 0.25 × 外购) / 运营天数"},
    {"key": "efficiencyDuration", "label_zh": "效能时长",           "format": "duration", "comparisons": ["wow", "mom"],   "good_direction": "down", "source": "confirmed", "formula_zh": "单均接单响应 + 平均等效制作"},
    {"key": "pickupCount",        "label_zh": "自取订单数",         "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "channel ∈ {1,2,3}"},
    {"key": "deliveryCount",      "label_zh": "外送订单数",         "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "channel ∈ {8,9,10}"},
    {"key": "freshMadeCount",     "label_zh": "现制商品数",         "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_item.one_category_name ∈ 现制类目"},
]

# City/region overlay — until t_shop_info exposes a region field for the NA tenant,
# we apply this static mapping. Update when the master adds the column.
STORE_GEO: dict[str, dict[str, str]] = {
    "US00001": {"city": "New York", "region": "Manhattan – Lower"},
    "US00002": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00003": {"city": "New York", "region": "Manhattan – Lower"},
    "US00004": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00005": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00006": {"city": "New York", "region": "Manhattan – Lower"},
    "US00008": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00012": {"city": "New York", "region": "Manhattan – Chelsea"},
    "US00020": {"city": "New York", "region": "Manhattan – Gramercy"},
    "US00024": {"city": "New York", "region": "Manhattan – Gramercy"},
    "US00025": {"city": "New York", "region": "Manhattan – Lower"},
    "US00027": {"city": "New York", "region": "Manhattan – Midtown"},
}


def date_window(days: int) -> list[str]:
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def main() -> None:
    print(f"[refresh] tenant={TENANT} retain_days={RETAIN_DAYS} half_hour_days={HALF_HOUR_RETAIN_DAYS}")

    # 1. Collect.
    print("[collect] store directory…")
    stores_raw = fetch_store_directory()
    print(f"  → {len(stores_raw)} stores in master")

    print("[collect] daily orders…")
    orders = fetch_daily_orders(RETAIN_DAYS)
    print(f"  → {len(orders)} (shop_no, et_date) rows")

    print("[collect] daily products…")
    products = fetch_daily_products(RETAIN_DAYS)
    print(f"  → {len(products)} (shop_no, et_date) product rows")

    print("[collect] spoilage…")
    spoilage = fetch_daily_spoilage(RETAIN_DAYS)
    print(f"  → {len(spoilage)} rows")

    print("[collect] half-hour efficiency…")
    half_hour_eff = fetch_half_hour_efficiency(HALF_HOUR_RETAIN_DAYS)
    print(f"  → {len(half_hour_eff)} slot rows")

    print("[collect] half-hour sales…")
    half_hour_sales = fetch_half_hour_sales(HALF_HOUR_RETAIN_DAYS)
    print(f"  → {len(half_hour_sales)} slot rows")

    print("[collect] SPU daily…")
    spu_raw = fetch_spu_daily(RETAIN_DAYS)
    print(f"  → {len(spu_raw)} (shop, date, spu) rows")

    # Health cross-check (best-effort; not part of payload).
    try:
        _ = fetch_open_store_counts(RETAIN_DAYS)
        _ = fetch_tenant_order_counters(RETAIN_DAYS)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] health cross-check failed (non-fatal): {exc}")

    # 2. Stores with geo overlay.
    stores = []
    for s in stores_raw:
        geo = STORE_GEO.get(s["shop_no"], {"city": "New York", "region": "Manhattan"})
        stores.append({
            "shop_no": s["shop_no"],
            "shop_name": s["shop_name"],
            "city": geo["city"],
            "region": geo["region"],
            "operating_today": bool(s["operating_today"]),
        })

    # 3. Aggregate.
    dates = date_window(RETAIN_DAYS)
    daily_rows = build_daily_store_rows(stores, orders, products, spoilage, dates)
    rollup_durations_into_daily(daily_rows, half_hour_eff)
    half_hour_eff_norm = normalize_half_hour_efficiency(half_hour_eff)
    half_hour_sales_norm = normalize_half_hour_sales(half_hour_sales)
    spu_norm = normalize_spu_daily(spu_raw)

    # 4. Build payload.
    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tenant": TENANT,
            "timezone": "America/New_York",
            "retained_from": dates[0] if dates else date.today().isoformat(),
            "retained_to": dates[-1] if dates else date.today().isoformat(),
            "schema_version": 1,
            "source_status": {m["key"]: m["source"] for m in METRICS},
        },
        "stores": stores,
        "metrics": METRICS,
        "daily_store_rows": daily_rows,
        "half_hour_rows": half_hour_eff_norm,
        "half_hour_sales_rows": half_hour_sales_norm,
        "spu_daily_rows": spu_norm,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"[done] wrote {OUTPUT} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
