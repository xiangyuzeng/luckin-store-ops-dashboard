"""End-to-end pipeline: read MySQL → aggregate → write data/payload.json.

Run on an internal host that can reach the four read replicas
(aws-luckyus-{salesorder,opshop,scm-shopstock,iluckyhealth}-rw) and has AWS
credentials with secretsmanager:GetSecretValue for MYSQL_SECRET_NAME.

    MYSQL_SECRET_NAME=<your-secret> python3 -m pipeline.frontend_formatter
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .collectors.bom import fetch_bom_avg, fetch_goods_unit_costs
from .collectors.efficiency import (
    fetch_half_hour_running_totals,
    fetch_half_hour_timing,
)
from .collectors.labor import fetch_daily_labor_hours
from .collectors.orders import (
    fetch_daily_store_fact,
    fetch_daily_timing,
    fetch_shop_id_to_shop_no_map,
    fetch_spu_code_daily,
    fetch_spu_daily,
)
from .collectors.qc import fetch_daily_qc
from .collectors.spoilage import fetch_daily_spoilage_by_spec
from .collectors.stores import fetch_store_directory

RETAIN_DAYS = int(os.environ.get("RETAIN_DAYS", "90"))
HALF_HOUR_RETAIN_DAYS = int(os.environ.get("HALF_HOUR_RETAIN_DAYS", "3"))
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "payload.json"
TENANT = os.environ.get("LUCKIN_TENANT", "LKUS")

# Mirrors lib/metrics.ts. With real production data, satisfaction is
# CONFIRMED (source = t_order_store_fact.{pickup,delivery}_dissatisfied_order_quantity).
METRICS: list[dict[str, Any]] = [
    {"key": "orderCount",         "label_zh": "订单数量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "已完成订单数 (t_order.status=90)"},
    {"key": "productCount",       "label_zh": "商品数量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "self_quantity + purchase_quantity 每店每日"},
    {"key": "satisfaction",       "label_zh": "满意度",            "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "1 − (自取不满意 + 外送不满意) / 订单总数"},
    {"key": "hourlyCups",         "label_zh": "小时杯量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "等效商品数 / SUM(t_emp_kpi.attendance_hours)"},
    {"key": "perfHourlyCups",     "label_zh": "绩效小时杯量",      "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "等效商品数 / SUM(t_emp_kpi.kpi_hours) — kpi_hours 已排除会议/培训/帮带训/休息"},
    {"key": "hourlyCupAchieve",   "label_zh": "小时杯量达成比",    "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "pending",   "formula_zh": "(绩效小时杯量 / 理论小时杯量) × 100%"},
    {"key": "qcPassRate",         "label_zh": "品控稽核达标率",    "format": "percent",  "comparisons": ["sequential"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "SUM(t_shopcheck_report.score≥80) / COUNT(*)  （t_shopcheck_report, status∈{10,40}, 0<score≤100）"},
    {"key": "qcAvgScore",         "label_zh": "品控稽核平均分",    "format": "score",    "comparisons": ["sequential"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "SUM(t_shopcheck_report.score) / COUNT(*)"},
    {"key": "materialLossRate",   "label_zh": "原料损耗率",        "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "down", "source": "confirmed", "formula_zh": "SUM(过期销毁 qty × goods_unit_cost) / SUM(sold qty × SUM(BOM need_qty × goods_unit_cost))  — goods_unit_cost 跨规格按收货量加权"},
    {"key": "avgDailyProducts",   "label_zh": "单店日均商品数",    "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_store_fact 商品数 / 运营天数"},
    {"key": "avgDailyFreshMade",  "label_zh": "单店日均现制商品数","format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "self_quantity / 运营天数"},
    {"key": "avgDailyEquiv",      "label_zh": "单店日均等效商品数","format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "(现制 + 0.25 × 外购) / 运营天数"},
    {"key": "efficiencyDuration", "label_zh": "效能时长",          "format": "duration", "comparisons": ["wow", "mom"],   "good_direction": "down", "source": "confirmed", "formula_zh": "单均接单响应 + 平均等效制作"},
    {"key": "pickupCount",        "label_zh": "自取订单数",        "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "channel ∈ {1,2,3}"},
    {"key": "deliveryCount",      "label_zh": "外送订单数",        "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "channel ∈ {8,9,10}"},
    {"key": "freshMadeCount",     "label_zh": "现制商品数",        "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "t_order_item.one_category_name = 'Drink'"},
]

# Manhattan-neighborhood overlay since t_shop_info.country_name etc. are NULL.
STORE_GEO: dict[str, dict[str, str]] = {
    "US00001": {"city": "New York", "region": "Manhattan – Greenwich Village"},
    "US00002": {"city": "New York", "region": "Manhattan – Chelsea / NoMad"},
    "US00003": {"city": "New York", "region": "Manhattan – Financial District"},
    "US00004": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00005": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00006": {"city": "New York", "region": "Manhattan – Financial District"},
    "US00007": {"city": "New York", "region": "Manhattan – Upper West Side"},
    "US00008": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00010": {"city": "New York", "region": "Manhattan – Greenwich Village"},
    "US00012": {"city": "New York", "region": "Manhattan – Chelsea / NoMad"},
    "US00015": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00018": {"city": "New York", "region": "Manhattan – Midtown"},
    "US00019": {"city": "New York", "region": "Manhattan – Chelsea / NoMad"},
    "US00020": {"city": "New York", "region": "Manhattan – Gramercy"},
    "US00022": {"city": "New York", "region": "Manhattan – Chelsea / NoMad"},
    "US00024": {"city": "New York", "region": "Manhattan – Gramercy"},
    "US00025": {"city": "New York", "region": "Manhattan – Lower Manhattan"},
    "US00027": {"city": "New York", "region": "Manhattan – Midtown"},
}


def _to_int(x):
    return 0 if x is None else int(x)


def _to_float(x):
    return 0.0 if x is None else float(x)


def _non_op(shop_no: str, d: str) -> dict[str, Any]:
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


def main() -> None:
    print(f"[refresh] tenant={TENANT} retain_days={RETAIN_DAYS} half_hour_days={HALF_HOUR_RETAIN_DAYS}")

    print("[collect] store directory…")
    master = fetch_store_directory()
    print(f"  → {len(master)} stores in master")

    print("[collect] shop_id ↔ shop_no map…")
    shop_id_to_no = fetch_shop_id_to_shop_no_map()
    print(f"  → {len(shop_id_to_no)} ids resolved")

    print("[collect] daily store-fact aggregates…")
    daily_facts = fetch_daily_store_fact(RETAIN_DAYS)
    print(f"  → {len(daily_facts)} (shop_id, et_date) rows")

    print("[collect] daily timing (accept/make)…")
    daily_timing = fetch_daily_timing(RETAIN_DAYS)
    print(f"  → {len(daily_timing)} rows")

    print("[collect] SPU daily…")
    spu_daily = fetch_spu_daily(RETAIN_DAYS)
    print(f"  → {len(spu_daily)} (shop, date, spu) rows")

    print("[collect] half-hour running totals…")
    halfhour_running = fetch_half_hour_running_totals(HALF_HOUR_RETAIN_DAYS)
    print(f"  → {len(halfhour_running)} rows")

    print("[collect] half-hour timing…")
    halfhour_timing = fetch_half_hour_timing(HALF_HOUR_RETAIN_DAYS)
    print(f"  → {len(halfhour_timing)} rows")

    print("[collect] spoilage by spec…")
    try:
        spoilage_by_spec = fetch_daily_spoilage_by_spec(RETAIN_DAYS)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] spoilage failed: {exc}")
        spoilage_by_spec = []
    print(f"  → {len(spoilage_by_spec)} rows")

    print("[collect] SPU code daily sales…")
    try:
        spu_code_daily = fetch_spu_code_daily(RETAIN_DAYS)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] spu_code_daily failed: {exc}")
        spu_code_daily = []
    print(f"  → {len(spu_code_daily)} rows")

    print("[collect] BOM avg + goods unit costs…")
    try:
        bom_rows = fetch_bom_avg()
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] BOM failed: {exc}")
        bom_rows = []
    try:
        goods_costs = fetch_goods_unit_costs()
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] goods costs failed: {exc}")
        goods_costs = []
    print(f"  → {len(bom_rows)} BOM rows, {len(goods_costs)} goods with cost")

    print("[collect] labor hours (attendance + KPI)…")
    try:
        labor = fetch_daily_labor_hours(RETAIN_DAYS)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] labor failed: {exc}")
        labor = []
    print(f"  → {len(labor)} rows")

    print("[collect] QC shop-check reports…")
    try:
        qc = fetch_daily_qc(RETAIN_DAYS)
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] qc failed: {exc}")
        qc = []
    print(f"  → {len(qc)} rows")

    # ── Build theoretical / loss cost lookups (cross-DB Python join) ─
    #   goods_cost[material_mid]   = weighted-avg unit cost (USD)
    #   spu_cost[spu_code]         = SUM over BOM ingredients of need_qty × goods_cost
    #   theoretical_cost_by[shop,d]= SUM over sold SPUs of sold_qty × spu_cost
    #   loss_cost_by[shop,d]       = SUM over spoiled specs of spoiled_qty × goods_cost
    # Materials missing from goods_cost contribute 0 (best-effort).
    goods_cost: dict[str, float] = {
        str(r["goods_mid"]): _to_float(r["unit_cost"]) for r in goods_costs
    }
    spu_cost: dict[str, float] = {}
    for r in bom_rows:
        spu = str(r["spu_code"])
        unit_cost = goods_cost.get(str(r["material_mid"]), 0.0)
        spu_cost[spu] = spu_cost.get(spu, 0.0) + _to_float(r["need_qty"]) * unit_cost

    theoretical_by: dict[tuple[int, str], float] = {}
    for r in spu_code_daily:
        key = (int(r["shop_id"]), str(r["et_date"]))
        cost = spu_cost.get(str(r["spu_code"]), 0.0)
        theoretical_by[key] = theoretical_by.get(key, 0.0) + _to_float(r["qty"]) * cost

    loss_by: dict[tuple[int, str], float] = {}
    for r in spoilage_by_spec:
        key = (int(r["shop_id"]), str(r["et_date"]))
        spec_mid = str(r["spec_mid"])
        goods_mid = spec_mid.split("-", 1)[0]
        cost = goods_cost.get(goods_mid, 0.0)
        loss_by[key] = loss_by.get(key, 0.0) + _to_float(r["spoiled_qty"]) * cost

    # ── Build daily store rows ──────────────────────────────────────
    timing_by = {(int(r["shop_id"]), str(r["et_date"])): r for r in daily_timing}
    facts_by = {(int(r["shop_id"]), str(r["et_date"])): r for r in daily_facts}
    labor_by = {(int(r["shop_id"]), str(r["et_date"])): r for r in labor}
    qc_by = {(int(r["shop_id"]), str(r["et_date"])): r for r in qc}
    dates = sorted({str(r["et_date"]) for r in daily_facts})
    if not dates:
        # No real data — bail rather than ship an empty payload.
        raise RuntimeError("No daily_facts data returned; aborting refresh.")

    daily_rows: list[dict[str, Any]] = []
    for m in master:
        shop_no = m["shop_no"]
        # Find this shop's id from any data row containing it.
        shop_id = next((sid for sid, sno in shop_id_to_no.items() if sno == shop_no), None)
        opened_on = m["set_up_time"]
        opened_iso = str(opened_on)[:10] if opened_on else None

        for d in dates:
            if opened_iso and d < opened_iso:
                daily_rows.append(_non_op(shop_no, d))
                continue
            if shop_id is None:
                daily_rows.append(_non_op(shop_no, d))
                continue
            f = facts_by.get((shop_id, d))
            if not f or _to_int(f["order_count"]) <= 0:
                daily_rows.append(_non_op(shop_no, d))
                continue
            orders = _to_int(f["order_count"])
            pickup = _to_int(f["pickup_count"])
            delivery = _to_int(f["delivery_count"])
            fresh = _to_int(f["fresh_made_count"])
            purchased = _to_int(f["purchased_count"])
            equiv = int(round(fresh + 0.25 * purchased))
            products = fresh + purchased
            unsat = _to_int(f["pickup_unsat"]) + _to_int(f["delivery_unsat"])

            t = timing_by.get((shop_id, d))
            if t and _to_int(t["orders"]) > 0:
                accept_total = _to_float(t["accept_secs"])
                make_total = _to_float(t["make_secs"])
                accept_weight = _to_int(t["orders"])
                make_weight = equiv
            else:
                accept_total = make_total = 0.0
                accept_weight = make_weight = 0

            l = labor_by.get((shop_id, d))
            labor_total = round(_to_float(l["labor_hours_total"]), 2) if l else None
            labor_productive = round(_to_float(l["labor_hours_productive"]), 2) if l else None

            q = qc_by.get((shop_id, d))
            if q and _to_int(q["report_count"]) > 0:
                report_count = _to_int(q["report_count"])
                qc_pass_pair = {"num": _to_int(q["pass_count"]), "den": report_count}
                qc_score_pair = {"num": _to_int(q["score_sum"]), "den": report_count}
            else:
                qc_pass_pair = None
                qc_score_pair = None

            # Loss rate is best-effort: when goods_cost is missing for every
            # spoiled spec on a day, `loss` ends up 0 and we'd misreport "0%
            # loss" instead of "unknown". Require both sides > 0 to publish.
            theoretical = theoretical_by.get((shop_id, d), 0.0)
            loss = loss_by.get((shop_id, d), 0.0)
            if theoretical > 0 and loss > 0:
                loss_pair = {"num": round(loss, 2), "den": round(theoretical, 2)}
            else:
                loss_pair = None

            daily_rows.append({
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
                "satisfaction": {"num": orders - unsat, "den": orders},
                "qc_pass_rate": qc_pass_pair,
                "qc_avg_score": qc_score_pair,
                "hourly_cup_achieve": None,
                "material_loss_rate": loss_pair,
                "labor_hours_total": labor_total,
                "labor_hours_productive": labor_productive,
                "accept_response_duration": (
                    {"total_seconds": round(accept_total, 2), "weight": accept_weight}
                    if accept_weight > 0 else None
                ),
                "make_duration": (
                    {"total_seconds": round(make_total, 2), "weight": make_weight}
                    if make_weight > 0 else None
                ),
            })

    # ── Half-hour SALES rows (deltas of running totals) ─────────────
    facts_sorted: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for r in halfhour_running:
        ts = str(r["local_begin_date"])
        date_part = ts[:10]
        slot = ts[11:16]
        facts_sorted.setdefault((int(r["shop_id"]), date_part), []).append({
            "slot": slot,
            "total": _to_int(r["total_order_quantity"]),
            "pickup": _to_int(r["pickup_order_quantity"]),
            "delivery": _to_int(r["delivery_order_quantity"]),
            "self": _to_int(r["self_quantity"]),
            "purchase": _to_int(r["purchase_quantity"]),
        })

    sales_rows: list[dict[str, Any]] = []
    for (shop_id, d), buckets in facts_sorted.items():
        shop_no = shop_id_to_no.get(shop_id)
        if not shop_no:
            continue
        buckets.sort(key=lambda b: b["slot"])
        prev = {"total": 0, "pickup": 0, "delivery": 0, "self": 0, "purchase": 0}
        for b in buckets:
            if b["total"] < prev["total"]:
                continue  # 23:30 reset bucket
            sales_rows.append({
                "shop_no": shop_no, "date": d, "slot": b["slot"],
                "pickup_count":   max(0, b["pickup"]   - prev["pickup"]),
                "delivery_count": max(0, b["delivery"] - prev["delivery"]),
                "fresh_made_count": max(0, b["self"]     - prev["self"]),
                "purchased_count":  max(0, b["purchase"] - prev["purchase"]),
            })
            prev = b

    # ── Half-hour EFFICIENCY rows (direct timings) ──────────────────
    eff_rows: list[dict[str, Any]] = []
    for r in halfhour_timing:
        shop_no = shop_id_to_no.get(int(r["shop_id"]))
        if not shop_no:
            continue
        orders = _to_int(r["orders"])
        eff_rows.append({
            "shop_no": shop_no,
            "date": str(r["et_date"]),
            "slot": r["slot"],
            "accept_response": (
                {"total_seconds": _to_float(r["accept_secs"]), "weight": orders}
                if orders > 0 else None
            ),
            "make_duration": (
                {"total_seconds": _to_float(r["make_secs"]), "weight": orders}
                if orders > 0 else None
            ),
            "order_count": orders,
            "equiv_product_count": 0,
        })

    # ── SPU daily rows ──────────────────────────────────────────────
    spu_rows: list[dict[str, Any]] = []
    for r in spu_daily:
        shop_no = shop_id_to_no.get(int(r["shop_id"]))
        if not shop_no:
            continue
        spu_rows.append({
            "shop_no": shop_no,
            "date": str(r["et_date"]),
            "spu_name": r["spu_name"],
            "quantity": int(r["qty"]),
        })

    # ── Store directory ─────────────────────────────────────────────
    latest = dates[-1]
    operating_today_ids = {r["shop_no"] for r in daily_rows if r["date"] == latest and r["operating"]}
    stores: list[dict[str, Any]] = []
    for m in master:
        shop_no = m["shop_no"]
        geo = STORE_GEO.get(shop_no, {"city": "New York", "region": "Manhattan"})
        opened_on = str(m["set_up_time"])[:10] if m["set_up_time"] else None
        stores.append({
            "shop_no": shop_no,
            "shop_name": m["shop_name"],
            "city": geo["city"],
            "region": geo["region"],
            "operating_today": shop_no in operating_today_ids,
            **({"opened_on": opened_on} if opened_on else {}),
        })

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tenant": TENANT,
            "timezone": "America/New_York",
            "retained_from": dates[0],
            "retained_to": dates[-1],
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

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"[done] wrote {OUTPUT} ({size_kb:.1f} KB)")
    print(f"  stores={len(stores)}  operating_today={len(operating_today_ids)}")
    print(f"  daily_rows={len(daily_rows)}  half_hour_eff={len(eff_rows)}  "
          f"half_hour_sales={len(sales_rows)}  spu_daily_rows={len(spu_rows)}")


if __name__ == "__main__":
    main()
