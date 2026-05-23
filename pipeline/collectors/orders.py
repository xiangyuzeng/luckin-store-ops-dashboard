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
    """Per (shop_id, ET-local date, spu_name) quantity for TOP-N — note column is sku_num."""
    sql = """
        SELECT
            o.shop_id,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern')) AS et_date,
            i.spu_name,
            SUM(i.sku_num)                                    AS qty
          FROM luckyus_sales_order.t_order o
          JOIN luckyus_sales_order.t_order_item i ON i.order_id = o.id
         WHERE o.tenant = %s
           AND o.status = 90
           AND o.pay_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
           AND i.spu_name IS NOT NULL
         GROUP BY o.shop_id, et_date, i.spu_name
         HAVING qty > 0
         ORDER BY o.shop_id, et_date, qty DESC
         LIMIT 500000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())
