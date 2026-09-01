"""Per-day per-store order aggregates.

Strategy (refined after live schema probe):
  - Daily totals come from `t_order_store_fact` (cycle_type=3), which is
    half-hourly running totals within the day. Use MAX(total_order_quantity)
    per (shop_id, DATE(local_begin_date)) to get the end-of-day total.
    The 23:30 bucket resets to 0 — filter it out.
  - The store_fact table also pre-computes pickup/delivery splits, 现制
    (self_quantity) vs 外购 (purchase_quantity) splits, the dissatisfied
    counts (satisfaction!), and make_seconds.
  - SPU TOP-N still comes from t_order_item.spu_name × sku_num (column is
    `sku_num`, NOT `qty`).
  - Per-order accept/make timings come from t_order ⋈ t_order_make.

All queries SELECT-only, WHERE tenant='LKUS'.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_daily_store_fact(retain_days: int = 90) -> list[dict[str, Any]]:
    """Per (shop_id, ET-local date) daily aggregates from t_order_store_fact.

    Returns one row per shop-day with all the pre-aggregated columns we need:
    order_count, pickup_count, delivery_count, fresh_made (self), purchased,
    dissatisfied (pickup + delivery), make_seconds.
    """
    sql = """
        SELECT
            f.shop_id,
            DATE(f.local_begin_date) AS et_date,
            MAX(f.total_order_quantity)              AS order_count,
            MAX(f.pickup_order_quantity)             AS pickup_count,
            MAX(f.delivery_order_quantity)           AS delivery_count,
            MAX(f.self_quantity)                     AS fresh_made_count,
            MAX(f.purchase_quantity)                 AS purchased_count,
            MAX(f.pickup_dissatisfied_order_quantity)   AS pickup_unsat,
            MAX(f.delivery_dissatisfied_order_quantity) AS delivery_unsat,
            MAX(f.make_seconds)                      AS make_seconds
          FROM luckyus_sales_order.t_order_store_fact f
         WHERE f.tenant = %s
           AND f.cycle_type = 3
           AND f.local_begin_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
         GROUP BY f.shop_id, et_date
         HAVING order_count > 0
         ORDER BY f.shop_id, et_date
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def fetch_shop_id_to_shop_no_map() -> dict[int, str]:
    """Resolve shop_id ↔ shop_number using a recent t_order sample."""
    sql = """
        SELECT DISTINCT shop_id, shop_number
          FROM luckyus_sales_order.t_order
         WHERE tenant = %s
           AND pay_time >= UTC_TIMESTAMP() - INTERVAL 30 DAY
         LIMIT 1000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT,))
            rows = cur.fetchall()
    return {int(r["shop_id"]): r["shop_number"] for r in rows}


def fetch_daily_timing(retain_days: int = 90) -> list[dict[str, Any]]:
    """Per (shop_id, ET-local date) accept-response + make duration totals.

    Defines:
      single-order accept response  =  SUM(accept_time - pay_time) / orders
      avg equivalent make duration  =  SUM(finish_time - accept_time) / orders
    """
    sql = """
        SELECT
            o.shop_id,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern')) AS et_date,
            COUNT(*)                                          AS orders,
            SUM(TIMESTAMPDIFF(SECOND, o.pay_time, m.accept_time))     AS accept_secs,
            SUM(TIMESTAMPDIFF(SECOND, m.accept_time, m.finish_time))  AS make_secs
          FROM luckyus_sales_order.t_order o
          JOIN luckyus_sales_order.t_order_make m ON m.order_id = o.id
         WHERE o.tenant = %s
           AND o.status = 90
           AND o.pay_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
           AND m.accept_time IS NOT NULL
           AND m.finish_time IS NOT NULL
         GROUP BY o.shop_id, et_date
         ORDER BY o.shop_id, et_date
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def fetch_spu_daily(retain_days: int = 90) -> list[dict[str, Any]]:
    """Per (shop_id, ET-local date, spu_code, spu_name) quantity — note column is sku_num.

    One scan, two consumers. The TOP-N display path groups this by spu_name
    (human-readable); the materialLossRate path groups it by spu_code (the join
    key of t_formula_average). Those used to be two collectors issuing SQL that
    differed only in that one column, and the cost of keeping them decoupled was
    measurable: 2026-09-01 slow-log analysis (LCNA-DBA-SQL-2026-0901-B, SQL-05 /
    SQL-06) found the pair scanning 2,090,481 and 2,090,482 rows on consecutive
    runs — the same 2.09M rows twice, 38.1 s + 21.8 s per day on the
    salesorder writer.

    Verified equivalent against production over a 3-day window before the
    change: name-only, code-only and re-grouped-merged all return 2,970 groups
    and 18,613 units, and every row carries both columns (no NULL on either
    side). The qty > 0 filter moves to the consumers, where it applies to the
    same groups the old HAVING did.
    """
    sql = """
        SELECT
            o.shop_id,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern')) AS et_date,
            i.spu_code,
            i.spu_name,
            SUM(i.sku_num)                                    AS qty
          FROM luckyus_sales_order.t_order o
          JOIN luckyus_sales_order.t_order_item i ON i.order_id = o.id
         WHERE o.tenant = %s
           AND o.status = 90
           AND o.pay_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
           AND (i.spu_name IS NOT NULL OR i.spu_code IS NOT NULL)
         GROUP BY o.shop_id, et_date, i.spu_code, i.spu_name
         ORDER BY o.shop_id, et_date
         LIMIT 500000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def aggregate_spu_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Collapse fetch_spu_daily() rows onto one SPU column, dropping empty keys.

    key is "spu_name" or "spu_code". Reproduces the old per-collector output,
    including the HAVING qty > 0 the two queries used to apply.
    """
    totals: dict[tuple[int, str, str], float] = {}
    for r in rows:
        value = r.get(key)
        if value is None:
            continue
        k = (int(r["shop_id"]), str(r["et_date"]), str(value))
        totals[k] = totals.get(k, 0) + float(r["qty"] or 0)
    return [
        {"shop_id": shop_id, "et_date": et_date, key: value, "qty": qty}
        for (shop_id, et_date, value), qty in sorted(totals.items())
        if qty > 0
    ]
