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
from zoneinfo import ZoneInfo

from .collectors.bom import fetch_bom_avg, fetch_goods_unit_costs
from .collectors.efficiency import (
    fetch_half_hour_running_totals,
    fetch_half_hour_timing,
)
from .collectors.labor import fetch_daily_labor_hours
from .collectors.orders import (
    aggregate_spu_rows,
    fetch_daily_store_fact,
    fetch_daily_timing,
    fetch_shop_id_to_shop_no_map,
    fetch_spu_daily,
)
from .collectors.qc import fetch_daily_qc
from .collectors.spoilage import fetch_daily_spoilage_by_spec
from .collectors.stores import fetch_store_directory
from .config.settings import THEORETICAL_HOURLY_CUPS

RETAIN_DAYS = int(os.environ.get("RETAIN_DAYS", "90"))
HALF_HOUR_RETAIN_DAYS = int(os.environ.get("HALF_HOUR_RETAIN_DAYS", "3"))

# The board keeps RETAIN_DAYS of history, but a day older than a few days does
# not change: its orders are closed and its spoilage is booked. Re-querying all
# 90 days every night made t_order's 90-day predicate cover essentially the
# whole table, so the optimizer dropped idx_pay_time and full-scanned — 20~48 s
# per query, 4.18M rows a night (LCNA-DBA-SQL-2026-0901-B, SQL-05/06/11). The
# same query shape over a 3-day window measures 0.15 s.
#
# So each run re-collects only the last INCREMENTAL_DAYS ET days and splices
# them into the previous payload. Late status changes are the reason this is 3
# and not 1. Anything that slipped through anyway is healed by the weekly full
# rebuild, which also backfills after an outage.
INCREMENTAL_DAYS = int(os.environ.get("INCREMENTAL_DAYS", "3"))
# Python weekday(): Monday=0 … Sunday=6.
FULL_REBUILD_WEEKDAY = int(os.environ.get("FULL_REBUILD_WEEKDAY", "6"))
FORCE_FULL_REBUILD = os.environ.get("FORCE_FULL_REBUILD", "").lower() in {"1", "true", "yes"}
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "payload.json"
TENANT = os.environ.get("LUCKIN_TENANT", "LKUS")
STORE_TZ = ZoneInfo("America/New_York")

# Mirrors lib/metrics.ts. With real production data, satisfaction is
# CONFIRMED (source = t_order_store_fact.{pickup,delivery}_dissatisfied_order_quantity).
METRICS: list[dict[str, Any]] = [
    {"key": "orderCount",         "label_zh": "订单数量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "已完成订单数 (t_order.status=90)"},
    {"key": "productCount",       "label_zh": "商品数量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "self_quantity + purchase_quantity 每店每日"},
    {"key": "satisfaction",       "label_zh": "满意度",            "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "1 − (自取不满意 + 外送不满意) / 订单总数"},
    {"key": "hourlyCups",         "label_zh": "小时杯量",          "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "等效商品数 / SUM(t_emp_kpi.attendance_hours)"},
    {"key": "perfHourlyCups",     "label_zh": "绩效小时杯量",      "format": "count",    "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "等效商品数 / SUM(t_emp_kpi.kpi_hours) — kpi_hours 已排除会议/培训/帮带训/休息"},
    {"key": "hourlyCupAchieve",   "label_zh": "小时杯量达成比",    "format": "percent",  "comparisons": ["wow", "mom"],   "good_direction": "up",   "source": "confirmed", "formula_zh": "绩效小时杯量 / THEORETICAL_HOURLY_CUPS (env, 默认 30 杯/h)"},
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_previous_payload() -> dict[str, Any] | None:
    """The payload from the last run, or None if it cannot be trusted."""
    if not OUTPUT.exists():
        print("[mode] no previous payload on disk")
        return None
    try:
        prev = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[mode] previous payload unreadable ({exc})")
        return None
    if prev.get("meta", {}).get("schema_version") != 1:
        print("[mode] previous payload has a different schema_version")
        return None
    if prev.get("meta", {}).get("tenant") != TENANT:
        print("[mode] previous payload belongs to another tenant")
        return None
    return prev


def _payload_leaves_a_gap(prev: dict[str, Any] | None, today_et: date) -> bool:
    """True if splicing onto this payload would leave days with no data.

    The fresh window starts INCREMENTAL_DAYS − 1 days back. If the previous
    payload ends before the day preceding that — a container that sat idle, an
    outage, a rebuild from an old image — the days in between belong to neither
    side, and an incremental run would write a hole into the history and keep it
    there until the next full rebuild.
    """
    if prev is None:
        return False
    retained_to = prev.get("meta", {}).get("retained_to")
    if not retained_to:
        return True
    earliest_fresh = today_et - timedelta(days=INCREMENTAL_DAYS - 1)
    return date.fromisoformat(str(retained_to)) < earliest_fresh - timedelta(days=1)


def _splice_rows(prev_rows: list[dict[str, Any]], fresh_rows: list[dict[str, Any]],
                 fresh_from: str, retain_from: str) -> list[dict[str, Any]]:
    """Freshly collected days replace their old versions; older days carry over.

    fresh_from is the first ET date this run re-collected in full. Everything on
    or after it comes from this run — a day whose rows are missing from the
    fresh set genuinely has no data now (a store that closed, a cancelled
    order), so carrying the old rows forward would resurrect them.
    """
    kept = [r for r in prev_rows if retain_from <= r["date"] < fresh_from]
    fresh = [r for r in fresh_rows if r["date"] >= fresh_from]
    return sorted(kept + fresh, key=lambda r: (r["date"], r.get("shop_no", "")))


# Collectors → set of metric keys they populate. Used to surface per-metric
# "last collector run" timestamps in the ?debug=1 overlay.
COLLECTOR_TO_METRICS: dict[str, list[str]] = {
    "orders": ["orderCount", "productCount", "satisfaction", "pickupCount", "deliveryCount", "freshMadeCount",
               "avgDailyProducts", "avgDailyFreshMade", "avgDailyEquiv"],
    "efficiency": ["efficiencyDuration"],
    "labor": ["hourlyCups", "perfHourlyCups", "hourlyCupAchieve"],
    "qc": ["qcPassRate", "qcAvgScore"],
    "spoilage_bom": ["materialLossRate"],
}


def main() -> None:
    print(f"[refresh] tenant={TENANT} retain_days={RETAIN_DAYS} half_hour_days={HALF_HOUR_RETAIN_DAYS}")
    collector_run_ts: dict[str, str] = {}

    # ── Collection window ───────────────────────────────────────────
    today_et = datetime.now(STORE_TZ).date()
    prev_payload = _load_previous_payload()
    stale_prev = _payload_leaves_a_gap(prev_payload, today_et)
    full_rebuild = (
        prev_payload is None
        or FORCE_FULL_REBUILD
        or today_et.weekday() == FULL_REBUILD_WEEKDAY
        or stale_prev
    )
    # One extra day of slack: the SQL window is "now − N days" in UTC, so the
    # oldest ET day it touches is only partly covered. fresh_from starts a day
    # later, and that day is whole.
    window_days = RETAIN_DAYS if full_rebuild else INCREMENTAL_DAYS + 1
    fresh_from = (today_et - timedelta(days=INCREMENTAL_DAYS - 1)).isoformat()
    retain_from = (today_et - timedelta(days=RETAIN_DAYS - 1)).isoformat()
    reason = ("forced" if FORCE_FULL_REBUILD else
              "no usable previous payload" if prev_payload is None else
              "previous payload too old to splice onto" if stale_prev else
              f"weekly rebuild (weekday={FULL_REBUILD_WEEKDAY})")
    if full_rebuild:
        print(f"[mode] FULL rebuild — {reason}; window={window_days}d")
    else:
        print(f"[mode] incremental — window={window_days}d, "
              f"re-collecting from {fresh_from}, retaining from {retain_from}")

    print("[collect] store directory…")
    master = fetch_store_directory()
    print(f"  → {len(master)} stores in master")

    print("[collect] shop_id ↔ shop_no map…")
    shop_id_to_no = fetch_shop_id_to_shop_no_map()
    print(f"  → {len(shop_id_to_no)} ids resolved")

    print("[collect] daily store-fact aggregates…")
    daily_facts = fetch_daily_store_fact(window_days)
    collector_run_ts["orders"] = _now_iso()
    print(f"  → {len(daily_facts)} (shop_id, et_date) rows")

    print("[collect] daily timing (accept/make)…")
    daily_timing = fetch_daily_timing(window_days)
    collector_run_ts["efficiency"] = _now_iso()
    print(f"  → {len(daily_timing)} rows")

    print("[collect] SPU daily (one scan, name + code)…")
    spu_combined = fetch_spu_daily(window_days)
    spu_daily = aggregate_spu_rows(spu_combined, "spu_name")
    spu_code_daily = aggregate_spu_rows(spu_combined, "spu_code")
    print(f"  → {len(spu_combined)} scanned rows → {len(spu_daily)} by name, "
          f"{len(spu_code_daily)} by code")

    print("[collect] half-hour running totals…")
    halfhour_running = fetch_half_hour_running_totals(HALF_HOUR_RETAIN_DAYS)
    print(f"  → {len(halfhour_running)} rows")

    print("[collect] half-hour timing…")
    halfhour_timing = fetch_half_hour_timing(HALF_HOUR_RETAIN_DAYS)
    print(f"  → {len(halfhour_timing)} rows")

    print("[collect] spoilage by spec…")
    try:
        spoilage_by_spec = fetch_daily_spoilage_by_spec(window_days)
        collector_run_ts["spoilage_bom"] = _now_iso()
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] spoilage failed: {exc}")
        spoilage_by_spec = []
    print(f"  → {len(spoilage_by_spec)} rows")

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
        labor = fetch_daily_labor_hours(window_days)
        collector_run_ts["labor"] = _now_iso()
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] labor failed: {exc}")
        labor = []
    print(f"  → {len(labor)} rows")

    print("[collect] QC shop-check reports…")
    try:
        qc = fetch_daily_qc(window_days)
        collector_run_ts["qc"] = _now_iso()
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

            # hourly_cup_achieve aggregates correctly via aggregateRatio:
            #   SUM(equiv) / (THEORETICAL × SUM(labor_productive))
            #   = (SUM(equiv) / SUM(labor_productive)) / THEORETICAL
            #   = perfHourlyCups / THEORETICAL
            if labor_productive and labor_productive > 0 and equiv > 0:
                achieve_pair = {
                    "num": equiv,
                    "den": round(labor_productive * THEORETICAL_HOURLY_CUPS, 2),
                }
            else:
                achieve_pair = None

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
                "hourly_cup_achieve": achieve_pair,
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

    # ── Splice this run's days into the retained history ────────────
    if not full_rebuild and prev_payload is not None:
        before = (len(daily_rows), len(spu_rows))
        daily_rows = _splice_rows(prev_payload.get("daily_store_rows", []),
                                  daily_rows, fresh_from, retain_from)
        spu_rows = _splice_rows(prev_payload.get("spu_daily_rows", []),
                                spu_rows, fresh_from, retain_from)
        print(f"[merge] daily_store_rows {before[0]} fresh → {len(daily_rows)} retained; "
              f"spu_daily_rows {before[1]} fresh → {len(spu_rows)} retained")

    retained_dates = sorted({r["date"] for r in daily_rows})
    if not retained_dates:
        raise RuntimeError("No daily rows after merge; aborting refresh.")

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tenant": TENANT,
            "timezone": "America/New_York",
            "retained_from": retained_dates[0],
            "retained_to": retained_dates[-1],
            # Which days this particular run actually queried. A reader chasing
            # a wrong number needs to know whether it was measured tonight or
            # carried over from an earlier run.
            "collection_mode": "full" if full_rebuild else "incremental",
            "collected_from": retained_dates[0] if full_rebuild else fresh_from,
            "schema_version": 1,
            "source_status": {m["key"]: m["source"] for m in METRICS},
            "collector_timestamps": {
                metric_key: collector_run_ts[collector]
                for collector, metric_keys in COLLECTOR_TO_METRICS.items()
                if collector in collector_run_ts
                for metric_key in metric_keys
            },
            "theoretical_hourly_cups": THEORETICAL_HOURLY_CUPS,
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
