"""Aggregate raw collector output into the shapes the frontend payload expects.

Inputs:
  - daily_orders          : per (shop_no, et_date) order + channel counts
  - daily_products        : per (shop_no, et_date) product + fresh/purchased counts
  - daily_spoilage        : per (shop_id, et_date) adjust units (partial source)
  - half_hour_efficiency  : per (shop_no, et_date, slot) timings
  - half_hour_sales       : per (shop_no, et_date, slot) channel + category split
  - spu_daily             : per (shop_no, et_date, spu_name) qty

Output: ready-to-emit dicts that match lib/types.ts.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def _key(shop_no: str, et_date: str) -> tuple[str, str]:
    return (shop_no, str(et_date))


def build_daily_store_rows(
    stores: Iterable[dict[str, Any]],
    orders: Iterable[dict[str, Any]],
    products: Iterable[dict[str, Any]],
    spoilage: Iterable[dict[str, Any]],
    dates: list[str],
) -> list[dict[str, Any]]:
    """Cross-join stores x dates and join the aggregates. Operating==True iff order_count > 0."""
    orders_by = {_key(r["shop_no"], r["et_date"]): r for r in orders}
    products_by = {_key(r["shop_no"], r["et_date"]): r for r in products}
    # Spoilage keyed by shop_id — we don't carry shop_id↔shop_no mapping in collectors;
    # for now we leave material_loss_rate null (theoretical denominator unmapped anyway).

    rows: list[dict[str, Any]] = []
    for s in stores:
        for d in dates:
            o = orders_by.get(_key(s["shop_no"], d))
            p = products_by.get(_key(s["shop_no"], d))
            order_count = int(o["order_count"]) if o else 0
            if order_count == 0:
                rows.append(_non_operating_row(s["shop_no"], d))
                continue
            fresh = int(p["fresh_made_count"]) if p and p.get("fresh_made_count") is not None else 0
            purchased = int(p["purchased_count"]) if p and p.get("purchased_count") is not None else 0
            equiv = round(fresh + 0.25 * purchased)
            products_total = int(p["product_count"]) if p and p.get("product_count") is not None else fresh + purchased

            rows.append({
                "shop_no": s["shop_no"],
                "date": d,
                "operating": True,
                "order_count": order_count,
                "pickup_count": int(o["pickup_count"] or 0) if o else None,
                "delivery_count": int(o["delivery_count"] or 0) if o else None,
                "product_count": products_total,
                "fresh_made_count": fresh,
                "purchased_count": purchased,
                "equiv_product_count": equiv,
                "avg_daily_products": products_total,
                "avg_daily_fresh_made": fresh,
                "avg_daily_equiv": equiv,
                # Pending sources → explicit nulls.
                "satisfaction": None,
                "qc_pass_rate": None,
                "qc_avg_score": None,
                "hourly_cup_achieve": None,
                "material_loss_rate": None,  # partial — actual numerator known, theoretical denominator pending
                "labor_hours_total": None,
                "labor_hours_productive": None,
                # Confirmed durations are aggregated from half-hour rows downstream.
                "accept_response_duration": None,
                "make_duration": None,
            })
    return rows


def _non_operating_row(shop_no: str, date: str) -> dict[str, Any]:
    return {
        "shop_no": shop_no, "date": date, "operating": False,
        "order_count": None, "pickup_count": None, "delivery_count": None,
        "product_count": None, "fresh_made_count": None, "purchased_count": None,
        "equiv_product_count": None, "avg_daily_products": None,
        "avg_daily_fresh_made": None, "avg_daily_equiv": None,
        "satisfaction": None, "qc_pass_rate": None, "qc_avg_score": None,
        "hourly_cup_achieve": None, "material_loss_rate": None,
        "labor_hours_total": None, "labor_hours_productive": None,
        "accept_response_duration": None, "make_duration": None,
    }


def rollup_durations_into_daily(
    daily_rows: list[dict[str, Any]],
    half_hour_eff: Iterable[dict[str, Any]],
) -> None:
    """Mutate daily_rows: aggregate accept/make durations from the half-hour table
    onto the matching per-store-day row as DurationPair structures."""
    accum: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"accept_total": 0.0, "make_total": 0.0, "order_w": 0.0, "equiv_w": 0.0}
    )
    for r in half_hour_eff:
        k = _key(r["shop_no"], r["et_date"])
        accept_t = float(r.get("accept_total_seconds") or 0)
        make_t = float(r.get("make_total_seconds") or 0)
        accum[k]["accept_total"] += accept_t
        accum[k]["make_total"] += make_t
        accum[k]["order_w"] += float(r.get("order_count") or 0)
        # equiv weight = fresh + 0.25*purchased; without per-slot product info here,
        # use order_count as a stable weight. The full per-slot fresh/purchased lives in half_hour_sales.
        accum[k]["equiv_w"] += float(r.get("order_count") or 0)

    by_key = {_key(r["shop_no"], r["date"]): r for r in daily_rows}
    for k, agg in accum.items():
        row = by_key.get(k)
        if not row or not row["operating"]:
            continue
        if agg["order_w"] > 0:
            row["accept_response_duration"] = {
                "total_seconds": round(agg["accept_total"], 2),
                "weight": int(agg["order_w"]),
            }
        if agg["equiv_w"] > 0:
            row["make_duration"] = {
                "total_seconds": round(agg["make_total"], 2),
                "weight": int(agg["equiv_w"]),
            }


def normalize_half_hour_efficiency(half_hour_eff: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in half_hour_eff:
        accept_t = r.get("accept_total_seconds")
        make_t = r.get("make_total_seconds")
        orders = int(r.get("order_count") or 0)
        out.append({
            "shop_no": r["shop_no"],
            "date": str(r["et_date"]),
            "slot": r["slot"],
            "accept_response": None if accept_t is None or orders == 0 else {
                "total_seconds": float(accept_t),
                "weight": orders,
            },
            "make_duration": None if make_t is None or orders == 0 else {
                "total_seconds": float(make_t),
                "weight": orders,
            },
            "order_count": orders,
            # equiv_count is computed at the sales-side rollup; here we leave 0 if not available.
            "equiv_product_count": 0,
        })
    return out


def normalize_half_hour_sales(half_hour_sales: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in half_hour_sales:
        out.append({
            "shop_no": r["shop_no"],
            "date": str(r["et_date"]),
            "slot": r["slot"],
            "pickup_count": int(r.get("pickup_count") or 0),
            "delivery_count": int(r.get("delivery_count") or 0),
            "fresh_made_count": int(r.get("fresh_made_count") or 0),
            "purchased_count": int(r.get("purchased_count") or 0),
        })
    return out


def normalize_spu_daily(spu_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "shop_no": r["shop_no"],
            "date": str(r["et_date"]),
            "spu_name": r["spu_name"],
            "quantity": int(r["quantity"]),
        }
        for r in spu_rows
    ]
