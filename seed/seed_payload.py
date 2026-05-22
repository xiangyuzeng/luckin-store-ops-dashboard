"""
Generate a realistic seed `data/payload.json` so the UI can be developed and
demoed end-to-end before the live pipeline is wired.

Conventions:
  - Real Luckin US store roster (US00001..US00027).
  - Plausible counts, believable morning + lunch peak.
  - Ratios carry raw numerator and denominator so client-side range
    aggregation as Sum-num / Sum-den works correctly.
  - Pending metrics emit `null` (satisfaction, QC pass rate, QC avg score,
    hourly cup achieve). Material loss rate is left null too because it
    requires BOM-based theoretical cost.
  - Generated payload conforms to lib/types.ts and is validated by
    scripts/validate_payload.ts.

Run:
  python3 seed/seed_payload.py
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

random.seed(42)

OUTPUT = Path(__file__).resolve().parent.parent / "data" / "payload.json"

# Confirmed store roster — sourced from /app/luckin-ops-dashboard/app/data/constants.js
STORES = [
    {"shop_no": "US00001", "shop_name": "8th & Broadway",   "city": "New York", "region": "Manhattan – Lower",   "opened_on": "2024-09-15"},
    {"shop_no": "US00002", "shop_name": "28th & 6th",       "city": "New York", "region": "Manhattan – Midtown", "opened_on": "2024-09-20"},
    {"shop_no": "US00003", "shop_name": "100 Maiden Ln",    "city": "New York", "region": "Manhattan – Lower",   "opened_on": "2024-10-05"},
    {"shop_no": "US00004", "shop_name": "37th & Broadway",  "city": "New York", "region": "Manhattan – Midtown", "opened_on": "2024-10-10"},
    {"shop_no": "US00005", "shop_name": "54th & 8th",       "city": "New York", "region": "Manhattan – Midtown", "opened_on": "2024-11-12"},
    {"shop_no": "US00006", "shop_name": "102 Fulton",       "city": "New York", "region": "Manhattan – Lower",   "opened_on": "2024-11-18"},
    {"shop_no": "US00008", "shop_name": "33rd & 10th",      "city": "New York", "region": "Manhattan – Midtown", "opened_on": "2024-12-03"},
    {"shop_no": "US00012", "shop_name": "16th & 6th",       "city": "New York", "region": "Manhattan – Chelsea", "opened_on": "2025-01-08"},
    {"shop_no": "US00020", "shop_name": "21st & 3rd",       "city": "New York", "region": "Manhattan – Gramercy","opened_on": "2025-02-25"},
    {"shop_no": "US00024", "shop_name": "15th & 3rd",       "city": "New York", "region": "Manhattan – Gramercy","opened_on": "2025-03-12"},
    {"shop_no": "US00025", "shop_name": "221 Grand",        "city": "New York", "region": "Manhattan – Lower",   "opened_on": "2025-04-08"},
    {"shop_no": "US00027", "shop_name": "52nd & Madison",   "city": "New York", "region": "Manhattan – Midtown", "opened_on": "2025-05-02"},
]

# Locked decision: operating_today = had >=1 completed order in the last 24h ET.
# Seed: nearly all stores operating; mark US00027 (latest) as non-operating to exercise the "-" UI path.
NON_OPERATING_TODAY = {"US00027"}

# Metric registry duplicated here to populate payload.metrics. The TS lib/metrics.ts is the source of truth;
# the pipeline reads from a generated JSON to keep them in sync. For the seed, we hand-list.
METRICS = [
    {"key": "orderCount",          "label_zh": "订单数量",          "format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "confirmed", "formula_zh": "已完成订单数 (t_order.status=已完成)"},
    {"key": "productCount",        "label_zh": "商品数量",          "format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "confirmed", "formula_zh": "已完成订单的商品数 (t_order_item ⋈ t_order)"},
    {"key": "satisfaction",        "label_zh": "满意度",            "format": "percent",  "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "pending",   "formula_zh": "1 − 不满意订单数 / 订单数"},
    {"key": "hourlyCups",          "label_zh": "小时杯量",          "format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "pending",   "formula_zh": "等效商品数 / 总工时"},
    {"key": "perfHourlyCups",      "label_zh": "绩效小时杯量",      "format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "pending",   "formula_zh": "等效商品数 / (考勤工时 − 会议 − 培训 − 帮带训)"},
    {"key": "hourlyCupAchieve",    "label_zh": "小时杯量达成比",    "format": "percent",  "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "pending",   "formula_zh": "(绩效小时杯量 / 理论小时杯量) × 100%"},
    {"key": "qcPassRate",          "label_zh": "品控稽核达标率",    "format": "percent",  "comparisons": ["sequential"],      "good_direction": "up",   "source": "pending",   "formula_zh": "≥80分稽核任务数 / 稽核任务数"},
    {"key": "qcAvgScore",          "label_zh": "品控稽核平均分",    "format": "score",    "comparisons": ["sequential"],      "good_direction": "up",   "source": "pending",   "formula_zh": "稽核总分 / 稽核任务数"},
    {"key": "materialLossRate",    "label_zh": "原料损耗率",        "format": "percent",  "comparisons": ["wow", "mom"],      "good_direction": "down", "source": "partial",   "formula_zh": "(实际 − 理论消耗成本) / 理论消耗成本"},
    {"key": "avgDailyProducts",    "label_zh": "单店日均商品数",    "format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_store_fact 商品数 / 运营天数"},
    {"key": "avgDailyFreshMade",   "label_zh": "单店日均现制商品数","format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_item 现制类目计数 / 运营天数"},
    {"key": "avgDailyEquiv",       "label_zh": "单店日均等效商品数","format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "confirmed", "formula_zh": "(现制 + 0.25 × 外购) / 运营天数"},
    {"key": "efficiencyDuration",  "label_zh": "效能时长",          "format": "duration", "comparisons": ["wow", "mom"],      "good_direction": "down", "source": "confirmed", "formula_zh": "单均接单响应 + 平均等效制作"},
    {"key": "pickupCount",         "label_zh": "自取订单数",        "format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "confirmed", "formula_zh": "channel ∈ {1,2,3}"},
    {"key": "deliveryCount",       "label_zh": "外送订单数",        "format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "confirmed", "formula_zh": "channel ∈ {8,9,10}"},
    {"key": "freshMadeCount",      "label_zh": "现制商品数",        "format": "count",    "comparisons": ["wow", "mom"],      "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_item.one_category_name ∈ 现制类目"},
]


def half_hour_slots():
    return [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]


def slot_demand_factor(slot: str) -> float:
    """Plausible NA store traffic curve — morning + lunch peaks."""
    h, m = int(slot[:2]), int(slot[3:])
    minutes = h * 60 + m
    # 7:00 AM dawn ramp; 8:30 AM morning peak; 12:30 PM lunch peak; quiet after 18:00.
    def bell(center_min: int, sigma_min: int, height: float) -> float:
        return height * pow(2.71828, -((minutes - center_min) ** 2) / (2 * sigma_min ** 2))
    base = 0.05
    return base + bell(8 * 60 + 30, 50, 1.0) + bell(12 * 60 + 30, 55, 0.85) + bell(15 * 60, 90, 0.25)


def daily_orders_for_store(shop_no: str, day_ix: int) -> int:
    """Daily order count: 500-650 base, dow effect, mild upward drift."""
    base = {"US00001": 640, "US00002": 600, "US00003": 580, "US00004": 590,
            "US00005": 560, "US00006": 540, "US00008": 520, "US00012": 500,
            "US00020": 490, "US00024": 470, "US00025": 450, "US00027": 430}.get(shop_no, 500)
    dow = (date.today() - timedelta(days=day_ix)).weekday()
    dow_mult = [1.05, 1.08, 1.10, 1.10, 1.05, 0.88, 0.78][dow]
    drift = 1 + (40 - day_ix) * 0.002  # slight upward over retention window
    noise = random.uniform(0.92, 1.08)
    return max(50, int(base * dow_mult * drift * noise))


def split_pickup_delivery(total: int):
    pickup_share = random.uniform(0.62, 0.72)
    pickup = int(round(total * pickup_share))
    return pickup, total - pickup


def equiv(fresh: int, purchased: int) -> int:
    return int(round(fresh + 0.25 * purchased))


def build_daily_store_rows(stores, days):
    rows = []
    today = date.today()
    for day_ix in range(days):
        d = today - timedelta(days=day_ix)
        for s in stores:
            opened_on = date.fromisoformat(s["opened_on"]) if s.get("opened_on") else None
            operating = opened_on is None or d >= opened_on
            if not operating:
                rows.append({
                    "shop_no": s["shop_no"], "date": d.isoformat(), "operating": False,
                    "order_count": None, "pickup_count": None, "delivery_count": None,
                    "product_count": None, "fresh_made_count": None, "purchased_count": None,
                    "equiv_product_count": None, "avg_daily_products": None,
                    "avg_daily_fresh_made": None, "avg_daily_equiv": None,
                    "satisfaction": None, "qc_pass_rate": None, "qc_avg_score": None,
                    "hourly_cup_achieve": None, "material_loss_rate": None,
                    "labor_hours_total": None, "labor_hours_productive": None,
                    "accept_response_duration": None, "make_duration": None,
                })
                continue
            order_count = daily_orders_for_store(s["shop_no"], day_ix)
            pickup_count, delivery_count = split_pickup_delivery(order_count)
            # Items per order ~1.4 fresh + 0.3 purchased
            fresh = int(round(order_count * random.uniform(1.30, 1.50)))
            purchased = int(round(order_count * random.uniform(0.25, 0.40)))
            products = fresh + purchased
            equiv_products = equiv(fresh, purchased)

            # Confirmed efficiency durations:
            accept_secs_per_order = random.uniform(35, 75)
            make_secs_per_equiv = random.uniform(95, 180)

            rows.append({
                "shop_no": s["shop_no"], "date": d.isoformat(), "operating": True,
                "order_count": order_count,
                "pickup_count": pickup_count,
                "delivery_count": delivery_count,
                "product_count": products,
                "fresh_made_count": fresh,
                "purchased_count": purchased,
                "equiv_product_count": equiv_products,
                "avg_daily_products": products,         # this row already represents a single store-day
                "avg_daily_fresh_made": fresh,
                "avg_daily_equiv": equiv_products,
                # Pending — emit null
                "satisfaction": None,
                "qc_pass_rate": None,
                "qc_avg_score": None,
                "hourly_cup_achieve": None,
                "material_loss_rate": None,
                "labor_hours_total": None,
                "labor_hours_productive": None,
                # Confirmed durations as { total_seconds, weight }
                "accept_response_duration": {
                    "total_seconds": round(accept_secs_per_order * order_count, 2),
                    "weight": order_count,
                },
                "make_duration": {
                    "total_seconds": round(make_secs_per_equiv * equiv_products, 2),
                    "weight": equiv_products,
                },
            })
    return rows


def build_half_hour_rows(stores, days):
    """Return (efficiency_rows, sales_rows) so we share the same demand curve / factors."""
    slots = half_hour_slots()
    eff_rows = []
    sales_rows = []
    today = date.today()
    # Per-half-hour rows for the last 3 days (keeps payload lean while exercising chart + tables).
    for day_ix in range(min(days, 3)):
        d = today - timedelta(days=day_ix)
        for s in stores:
            opened_on = date.fromisoformat(s["opened_on"]) if s.get("opened_on") else None
            if opened_on and d < opened_on:
                continue
            daily_total = daily_orders_for_store(s["shop_no"], day_ix)
            pickup_share_day = random.uniform(0.62, 0.72)
            factors = [slot_demand_factor(slot) for slot in slots]
            total = sum(factors)
            for slot, f in zip(slots, factors):
                orders = max(0, int(round(daily_total * (f / total))))
                if orders == 0:
                    eff_rows.append({
                        "shop_no": s["shop_no"], "date": d.isoformat(), "slot": slot,
                        "accept_response": None, "make_duration": None,
                        "order_count": 0, "equiv_product_count": 0,
                    })
                    sales_rows.append({
                        "shop_no": s["shop_no"], "date": d.isoformat(), "slot": slot,
                        "pickup_count": 0, "delivery_count": 0,
                        "fresh_made_count": 0, "purchased_count": 0,
                    })
                    continue
                fresh = int(round(orders * random.uniform(1.30, 1.50)))
                purchased = int(round(orders * random.uniform(0.06, 0.12)))  # mockup: ~7.72% purchased
                equiv_products = equiv(fresh, purchased)
                pickup = int(round(orders * pickup_share_day * random.uniform(0.92, 1.05)))
                pickup = max(0, min(orders, pickup))
                delivery = orders - pickup
                accept_per = random.uniform(30, 90)
                make_per = random.uniform(90, 200)
                eff_rows.append({
                    "shop_no": s["shop_no"], "date": d.isoformat(), "slot": slot,
                    "accept_response": {"total_seconds": round(accept_per * orders, 2), "weight": orders},
                    "make_duration": {"total_seconds": round(make_per * equiv_products, 2), "weight": equiv_products},
                    "order_count": orders,
                    "equiv_product_count": equiv_products,
                })
                sales_rows.append({
                    "shop_no": s["shop_no"], "date": d.isoformat(), "slot": slot,
                    "pickup_count": pickup,
                    "delivery_count": delivery,
                    "fresh_made_count": fresh,
                    "purchased_count": purchased,
                })
    return eff_rows, sales_rows


# 20-item realistic Luckin US menu (Chinese names; reflective of actual menu).
SPU_MENU = [
    ("生椰拿铁",          0.180),
    ("丝绒拿铁",          0.085),
    ("美式咖啡",          0.082),
    ("冰摇美式",          0.060),
    ("拿铁咖啡",          0.058),
    ("橙C冰美式",         0.055),
    ("陨石生酪拿铁",      0.050),
    ("茉莉花香拿铁",      0.045),
    ("瑞纳冰",            0.042),
    ("百利甜风味拿铁",    0.040),
    ("焦糖玛奇朵",        0.038),
    ("摩卡咖啡",          0.035),
    ("卡布奇诺",          0.032),
    ("橘金气泡美式",      0.030),
    ("生椰丝绒拿铁",      0.028),
    ("草莓椰云拿铁",      0.026),
    ("抹茶拿铁",          0.024),
    ("茶咖系列",          0.022),
    ("巧克力风味饮",      0.020),
    ("其他",              0.049),  # remainder bucket (purchased goods etc.)
]


def build_spu_daily_rows(stores, days):
    """For each operating store-day, distribute the day's product quantity across the menu mix."""
    rows = []
    today = date.today()
    for day_ix in range(days):
        d = today - timedelta(days=day_ix)
        for s in stores:
            opened_on = date.fromisoformat(s["opened_on"]) if s.get("opened_on") else None
            if opened_on and d < opened_on:
                continue
            order_count = daily_orders_for_store(s["shop_no"], day_ix)
            # ~1.6 products per order (fresh + purchased combined).
            day_products = int(round(order_count * random.uniform(1.50, 1.75)))
            for spu_name, weight in SPU_MENU:
                qty = int(round(day_products * weight * random.uniform(0.85, 1.15)))
                if qty <= 0:
                    continue
                rows.append({
                    "shop_no": s["shop_no"],
                    "date": d.isoformat(),
                    "spu_name": spu_name,
                    "quantity": qty,
                })
    return rows


def build_payload(days: int = 40) -> dict:
    today = date.today()
    retained_from = (today - timedelta(days=days - 1)).isoformat()
    retained_to = today.isoformat()

    stores_with_flag = []
    for s in STORES:
        stores_with_flag.append({
            **s,
            "operating_today": s["shop_no"] not in NON_OPERATING_TODAY,
        })

    source_status = {m["key"]: m["source"] for m in METRICS}
    eff_rows, sales_rows = build_half_hour_rows(stores_with_flag, days)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tenant": "LKUS",
            "timezone": "America/New_York",
            "retained_from": retained_from,
            "retained_to": retained_to,
            "schema_version": 1,
            "source_status": source_status,
        },
        "stores": stores_with_flag,
        "metrics": METRICS,
        "daily_store_rows": build_daily_store_rows(stores_with_flag, days),
        "half_hour_rows": eff_rows,
        "half_hour_sales_rows": sales_rows,
        "spu_daily_rows": build_spu_daily_rows(stores_with_flag, days),
        # precomputed_comparisons: omitted for the seed; comparisons compute from retained data.
    }


def main():
    payload = build_payload()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Wrote {OUTPUT} ({size_kb:.1f} KB)")
    print(f"  stores={len(payload['stores'])}  daily_rows={len(payload['daily_store_rows'])}  "
          f"half_hour_rows={len(payload['half_hour_rows'])}  half_hour_sales={len(payload['half_hour_sales_rows'])}  "
          f"spu_daily_rows={len(payload['spu_daily_rows'])}")


if __name__ == "__main__":
    main()
