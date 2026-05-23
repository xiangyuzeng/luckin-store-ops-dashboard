"""
Build `data/payload.json` from real Luckin Coffee NA MySQL data extracted via
mcp-db-gateway. Consumes the JSON dumps in /tmp/luckin_real/ and emits a
payload that conforms to lib/types.ts.

Run from repo root:
    python3 pipeline/build_real_payload.py

Sources:
    /tmp/luckin_real/daily_facts.json    — per shop_id × date MAX of t_order_store_fact
    /tmp/luckin_real/daily_timing.json   — per shop_id × date SUM(accept-pay), SUM(finish-accept)
    /tmp/luckin_real/halfhour_facts.json — per shop_id × half-hour running totals (last 3-4 days)
    /tmp/luckin_real/halfhour_timing.json — per shop_id × half-hour SUM(accept-pay) etc.
    /tmp/luckin_real/spu_daily.json      — per shop_id × date × spu_name SUM(sku_num)
    /tmp/luckin_real/spoilage.json       — per shop_dept_id × date SUM(|adjust_num|) for reason 015
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "payload.json"
SRC = Path("/tmp/luckin_real")

# ──────────────────────────────────────────────────────────────────────
# Store roster — 18 production stores. shop_id↔shop_no↔shop_name mapping
# resolved from t_order and t_shop_info via mcp-db-gateway probe.
# city/region are static overlays since t_shop_info.country_name etc. are NULL.
# ──────────────────────────────────────────────────────────────────────
STORES = [
    # shop_id, shop_no,   shop_name,             city,        region,                              set_up_time (date only)
    (1127,  "US00001", "8th & Broadway",       "New York", "Manhattan – Greenwich Village",     "2025-06-30"),
    (1128,  "US00002", "28th & 6th",           "New York", "Manhattan – Chelsea / NoMad",        "2025-06-30"),
    (1140,  "US00003", "100 Maiden Ln",        "New York", "Manhattan – Financial District",     "2025-09-09"),
    (20011, "US00004", "37th & Broadway",      "New York", "Manhattan – Midtown",                "2025-11-20"),
    (1141,  "US00005", "54th & 8th",           "New York", "Manhattan – Midtown",                "2025-08-24"),
    (20010, "US00006", "102 Fulton",           "New York", "Manhattan – Financial District",     "2025-08-28"),
    (20009, "US00007", "108th & Broadway",     "New York", "Manhattan – Upper West Side",        "2026-04-30"),
    (20008, "US00008", "33rd & 10th",          "New York", "Manhattan – Midtown",                "2025-12-01"),
    (20016, "US00010", "154 Bleecker",         "New York", "Manhattan – Greenwich Village",      "2026-04-28"),
    (20019, "US00012", "16th & 6th",           "New York", "Manhattan – Chelsea / NoMad",        "2026-03-23"),
    (20022, "US00015", "41st & Lexington",     "New York", "Manhattan – Midtown",                "2026-04-30"),
    (20025, "US00018", "40th & 10th",          "New York", "Manhattan – Midtown",                "2026-05-20"),
    (20026, "US00019", "29th & 3rd",           "New York", "Manhattan – Chelsea / NoMad",        "2026-04-11"),
    (20027, "US00020", "21st & 3rd",           "New York", "Manhattan – Gramercy",               "2026-02-06"),
    (20029, "US00022", "23rd & 8th",           "New York", "Manhattan – Chelsea / NoMad",        "2026-05-20"),
    (20031, "US00024", "15th & 3rd",           "New York", "Manhattan – Gramercy",               "2025-12-14"),
    (20032, "US00025", "221 Grand",            "New York", "Manhattan – Lower Manhattan",        "2025-12-15"),
    (20035, "US00027", "52nd & Madison",       "New York", "Manhattan – Midtown",                "2026-02-26"),
]

SHOP_ID_TO_NO = {row[0]: row[1] for row in STORES}

# Metric registry (mirrors lib/metrics.ts).
# Key change vs seed: `satisfaction` is now CONFIRMED — real source is
# t_order_store_fact.{pickup,delivery}_dissatisfied_order_quantity.
METRICS = [
    {"key": "orderCount",         "label_zh": "订单数量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "已完成订单数 (t_order.status=已完成)"},
    {"key": "productCount",       "label_zh": "商品数量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "已完成订单的商品数 (t_order_item ⋈ t_order)"},
    {"key": "satisfaction",       "label_zh": "满意度",            "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "1 − (自取不满意 + 外送不满意) / 订单总数"},
    {"key": "hourlyCups",         "label_zh": "小时杯量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "pending",   "formula_zh": "等效商品数 / 总工时（考勤源待接入）"},
    {"key": "perfHourlyCups",     "label_zh": "绩效小时杯量",      "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "pending",   "formula_zh": "等效商品数 / (考勤工时 − 会议 − 培训 − 帮带训)"},
    {"key": "hourlyCupAchieve",   "label_zh": "小时杯量达成比",    "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "pending",   "formula_zh": "(绩效小时杯量 / 理论小时杯量) × 100%"},
    {"key": "qcPassRate",         "label_zh": "品控稽核达标率",    "format": "percent",  "comparisons": ["sequential"],   "good_direction": "up",   "source": "pending",   "formula_zh": "≥80分稽核任务数 / 稽核任务数（品控源待接入）"},
    {"key": "qcAvgScore",         "label_zh": "品控稽核平均分",    "format": "score",    "comparisons": ["sequential"],   "good_direction": "up",   "source": "pending",   "formula_zh": "稽核总分 / 稽核任务数"},
    {"key": "materialLossRate",   "label_zh": "原料损耗率",        "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "down", "source": "partial",   "formula_zh": "(实际 − 理论消耗成本) / 理论消耗成本（BOM 理论值待接入）"},
    {"key": "avgDailyProducts",   "label_zh": "单店日均商品数",    "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_store_fact 商品数 / 运营天数"},
    {"key": "avgDailyFreshMade",  "label_zh": "单店日均现制商品数","format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "self_quantity (现制) / 运营天数"},
    {"key": "avgDailyEquiv",      "label_zh": "单店日均等效商品数","format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "(现制 + 0.25 × 外购) / 运营天数"},
    {"key": "efficiencyDuration", "label_zh": "效能时长",          "format": "duration", "comparisons": ["wow", "mom"],   "good_direction": "down", "source": "confirmed", "formula_zh": "单均接单响应 + 平均等效制作"},
    {"key": "pickupCount",        "label_zh": "自取订单数",        "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "channel ∈ {1,2,3} (Mini Program / Own App / POS)"},
    {"key": "deliveryCount",      "label_zh": "外送订单数",        "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "channel ∈ {8,9,10} (UberEats / DoorDash / Grubhub)"},
    {"key": "freshMadeCount",     "label_zh": "现制商品数",        "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_item.one_category_name = 'Drink'"},
]


def load(name):
    with (SRC / name).open() as f:
        return json.load(f)


def to_int(x):
    return 0 if x is None else int(x)


def to_float(x):
    return 0.0 if x is None else float(x)


def build_daily_rows(daily_facts, daily_timing, spoilage):
    """One row per (shop_no, date) over the window. Operating iff order_count > 0."""
    timing_by = {(r["shop_id"], r["et_date"]): r for r in daily_timing}
    spoilage_by = {(r["shop_dept_id"], r["et_date"]): r for r in spoilage}

    rows = []
    # First pass: discover the full date set
    dates = sorted({r["et_date"] for r in daily_facts})

    facts_by = {(r["shop_id"], r["et_date"]): r for r in daily_facts}

    for shop_id, shop_no, _name, _city, _region, opened_on in STORES:
        for d in dates:
            if d < opened_on:
                rows.append(_non_operating(shop_no, d))
                continue
            f = facts_by.get((shop_id, d))
            if not f:
                rows.append(_non_operating(shop_no, d))
                continue
            orders = to_int(f["order_count"])
            if orders <= 0:
                rows.append(_non_operating(shop_no, d))
                continue
            pickup = to_int(f["pickup_count"])
            delivery = to_int(f["delivery_count"])
            fresh = to_int(f["fresh_made_count"])
            purchased = to_int(f["purchased_count"])
            equiv = int(round(fresh + 0.25 * purchased))
            products = fresh + purchased
            unsat = to_int(f["pickup_unsat"]) + to_int(f["delivery_unsat"])

            t = timing_by.get((shop_id, d))
            if t and to_int(t["orders"]) > 0:
                accept_total = to_float(t["accept_secs"])
                make_total = to_float(t["make_secs"])
                accept_weight = to_int(t["orders"])
                make_weight = equiv  # weight by equiv items per the spec
            else:
                accept_total = make_total = 0.0
                accept_weight = make_weight = 0

            # Material loss: actual events known, theoretical denominator UNMAPPED.
            # Keep null to honor the pending discipline.
            _sp = spoilage_by.get((shop_id, d))  # noqa: F841 — used in future when BOM is available

            rows.append({
                "shop_no": shop_no, "date": d, "operating": True,
                "order_count": orders,
                "pickup_count": pickup,
                "delivery_count": delivery,
                "product_count": products,
                "fresh_made_count": fresh,
                "purchased_count": purchased,
                "equiv_product_count": equiv,
                "avg_daily_products": products,
                "avg_daily_fresh_made": fresh,
                "avg_daily_equiv": equiv,
                # CONFIRMED — real source from t_order_store_fact.
                "satisfaction": {"num": orders - unsat, "den": orders},
                # Pending — sources not mapped yet.
                "qc_pass_rate": None,
                "qc_avg_score": None,
                "hourly_cup_achieve": None,
                "material_loss_rate": None,
                "labor_hours_total": None,
                "labor_hours_productive": None,
                # CONFIRMED — real timings from t_order + t_order_make.
                "accept_response_duration": {
                    "total_seconds": round(accept_total, 2),
                    "weight": accept_weight,
                } if accept_weight > 0 else None,
                "make_duration": {
                    "total_seconds": round(make_total, 2),
                    "weight": make_weight,
                } if make_weight > 0 else None,
            })
    return rows, dates


def _non_operating(shop_no, d):
    return {
        "shop_no": shop_no, "date": d, "operating": False,
        "order_count": None, "pickup_count": None, "delivery_count": None,
        "product_count": None, "fresh_made_count": None, "purchased_count": None,
        "equiv_product_count": None, "avg_daily_products": None,
        "avg_daily_fresh_made": None, "avg_daily_equiv": None,
        "satisfaction": None, "qc_pass_rate": None, "qc_avg_score": None,
        "hourly_cup_achieve": None, "material_loss_rate": None,
        "labor_hours_total": None, "labor_hours_productive": None,
        "accept_response_duration": None, "make_duration": None,
    }


def build_halfhour_rows(halfhour_facts, halfhour_timing):
    """Half-hour SALES rows (deltas of running totals) + EFFICIENCY rows (direct timings)."""
    # ── Sales rows: compute per-slot deltas from running totals.
    facts_sorted = {}
    for r in halfhour_facts:
        shop_id = r["shop_id"]
        # local_begin_date is "YYYY-MM-DD HH:MM:SS" string
        ts = r["local_begin_date"]
        date_part, time_part = ts.split(" ")
        slot = time_part[:5]  # "HH:MM"
        facts_sorted.setdefault((shop_id, date_part), []).append({
            "slot": slot,
            "total": to_int(r["total_order_quantity"]),
            "pickup": to_int(r["pickup_order_quantity"]),
            "delivery": to_int(r["delivery_order_quantity"]),
            "self": to_int(r["self_quantity"]),
            "purchase": to_int(r["purchase_quantity"]),
            "make_seconds": to_int(r["make_seconds"]),
        })

    sales_rows = []
    for (shop_id, d), buckets in facts_sorted.items():
        shop_no = SHOP_ID_TO_NO.get(shop_id)
        if not shop_no:
            continue
        buckets.sort(key=lambda b: b["slot"])
        prev = {"total": 0, "pickup": 0, "delivery": 0, "self": 0, "purchase": 0}
        for b in buckets:
            # Skip the end-of-day reset bucket (23:30 drops to 0).
            if b["total"] < prev["total"]:
                continue
            sales_rows.append({
                "shop_no": shop_no,
                "date": d,
                "slot": b["slot"],
                "pickup_count": max(0, b["pickup"] - prev["pickup"]),
                "delivery_count": max(0, b["delivery"] - prev["delivery"]),
                "fresh_made_count": max(0, b["self"] - prev["self"]),
                "purchased_count": max(0, b["purchase"] - prev["purchase"]),
            })
            prev = b

    # ── Efficiency rows: direct from t_order + t_order_make per slot.
    eff_rows = []
    for r in halfhour_timing:
        shop_no = SHOP_ID_TO_NO.get(r["shop_id"])
        if not shop_no:
            continue
        orders = to_int(r["orders"])
        eff_rows.append({
            "shop_no": shop_no,
            "date": r["et_date"],
            "slot": r["slot"],
            "accept_response": {
                "total_seconds": to_float(r["accept_secs"]),
                "weight": orders,
            } if orders > 0 else None,
            "make_duration": {
                "total_seconds": to_float(r["make_secs"]),
                "weight": orders,
            } if orders > 0 else None,
            "order_count": orders,
            "equiv_product_count": 0,  # not aggregated separately; OK for chart purposes
        })
    return eff_rows, sales_rows


def build_spu_rows(spu_daily):
    out = []
    for r in spu_daily:
        shop_no = SHOP_ID_TO_NO.get(r["shop_id"])
        if not shop_no:
            continue
        out.append({
            "shop_no": shop_no,
            "date": r["et_date"],
            "spu_name": r["spu_name"],
            "quantity": int(r["qty"]),
        })
    return out


def main():
    daily_facts = load("daily_facts.json")
    daily_timing = load("daily_timing.json")
    halfhour_facts = load("halfhour_facts.json")
    halfhour_timing = load("halfhour_timing.json")
    spu_daily = load("spu_daily.json")
    spoilage = load("spoilage.json")

    daily_rows, dates = build_daily_rows(daily_facts, daily_timing, spoilage)
    eff_rows, sales_rows = build_halfhour_rows(halfhour_facts, halfhour_timing)
    spu_rows = build_spu_rows(spu_daily)

    # operating_today = had >=1 completed order on the latest date in the window.
    latest = max(dates) if dates else ""
    operating_today_ids = {r["shop_no"] for r in daily_rows if r["date"] == latest and r["operating"]}

    stores = []
    for shop_id, shop_no, name, city, region, opened_on in STORES:
        stores.append({
            "shop_no": shop_no,
            "shop_name": name,
            "city": city,
            "region": region,
            "operating_today": shop_no in operating_today_ids,
            "opened_on": opened_on,
        })

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tenant": "LKUS",
            "timezone": "America/New_York",
            "retained_from": min(dates) if dates else "",
            "retained_to": max(dates) if dates else "",
            "schema_version": 1,
            "source_status": {m["key"]: m["source"] for m in METRICS},
        },
        "stores": stores,
        "metrics": METRICS,
        "daily_store_rows": daily_rows,
        "half_hour_rows": eff_rows,
        "half_hour_sales_rows": sales_rows,
        "spu_daily_rows": spu_rows,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT} ({size_kb:.1f} KB)")
    print(f"  stores={len(stores)}  operating_today={len(operating_today_ids)}")
    print(f"  retained: {payload['meta']['retained_from']} → {payload['meta']['retained_to']}")
    print(f"  daily_rows={len(daily_rows)}  half_hour_eff={len(eff_rows)}  "
          f"half_hour_sales={len(sales_rows)}  spu_daily_rows={len(spu_rows)}")


if __name__ == "__main__":
    main()
