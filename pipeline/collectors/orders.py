"""Per-day per-store order + product aggregates.

All timestamps in MySQL are stored UTC; we bucket to US/Eastern via CONVERT_TZ
so the day boundary matches operations (DST-aware via MySQL's tz tables).

Channel codes are confirmed: 1=Mini Program, 2=Own App, 3=POS/Walk-in (自取);
8=UberEats, 9=DoorDash, 10=Grubhub (外送).

Item-category split: t_order_item.one_category_name distinguishes 现制 (freshly
made) from 外购 (purchased goods). Categories are matched by name; collectors
return the raw split and the formatter applies the equiv-product formula
(equiv = fresh + 0.25 * purchased) downstream.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect

# Heuristic for fresh-made vs purchased — refined from t_order_item.one_category_name samples.
# Keeping the list explicit so changes are reviewed in code, not patched in production.
FRESH_CATEGORIES = ("现制", "现制饮品", "咖啡", "茶饮", "鲜萃", "Beverage")


def fetch_daily_orders(retain_days: int = 40) -> list[dict[str, Any]]:
    """One row per (shop_no, ET-local date) over the retained window."""
    sql = """
        SELECT
            o.shop_number                                                   AS shop_no,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern'))               AS et_date,
            COUNT(*)                                                        AS order_count,
            SUM(CASE WHEN o.channel IN (1, 2, 3)  THEN 1 ELSE 0 END)        AS pickup_count,
            SUM(CASE WHEN o.channel IN (8, 9, 10) THEN 1 ELSE 0 END)        AS delivery_count
          FROM luckyus_sales_order.t_order o
         WHERE o.tenant = %s
           AND o.status = '已完成'
           AND o.pay_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
         GROUP BY o.shop_number, et_date
         ORDER BY o.shop_number, et_date
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def fetch_daily_products(retain_days: int = 40) -> list[dict[str, Any]]:
    """Per (shop_no, ET-local date) product counts: total / fresh-made / purchased."""
    fresh_in = ", ".join(["%s"] * len(FRESH_CATEGORIES))
    sql = f"""
        SELECT
            o.shop_number                                                   AS shop_no,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern'))               AS et_date,
            SUM(i.qty)                                                      AS product_count,
            SUM(CASE WHEN i.one_category_name IN ({fresh_in}) THEN i.qty ELSE 0 END) AS fresh_made_count,
            SUM(CASE WHEN i.one_category_name NOT IN ({fresh_in}) OR i.one_category_name IS NULL THEN i.qty ELSE 0 END) AS purchased_count
          FROM luckyus_sales_order.t_order o
          JOIN luckyus_sales_order.t_order_item i ON i.order_id = o.id
         WHERE o.tenant = %s
           AND o.status = '已完成'
           AND o.pay_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
         GROUP BY o.shop_number, et_date
         ORDER BY o.shop_number, et_date
         LIMIT 100000
    """
    assert_read_only(sql)
    params = [*FRESH_CATEGORIES, *FRESH_CATEGORIES, TENANT, retain_days]
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def fetch_store_day_facts(retain_days: int = 40) -> list[dict[str, Any]]:
    """Authoritative per-store-day totals (cycle_type=3 = daily aggregate)."""
    sql = """
        SELECT
            sf.shop_id,
            sf.local_begin_date AS et_date,
            sf.total_order_quantity
          FROM luckyus_sales_order.t_order_store_fact sf
         WHERE sf.tenant = %s
           AND sf.cycle_type = 3
           AND sf.local_begin_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
         ORDER BY sf.shop_id, sf.local_begin_date
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def fetch_spu_daily(retain_days: int = 40) -> list[dict[str, Any]]:
    """Per (shop_no, ET-local date, spu_name) quantity — feeds the TOP10 table."""
    sql = """
        SELECT
            o.shop_number                                                   AS shop_no,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern'))               AS et_date,
            i.spu_name                                                      AS spu_name,
            SUM(i.qty)                                                      AS quantity
          FROM luckyus_sales_order.t_order o
          JOIN luckyus_sales_order.t_order_item i ON i.order_id = o.id
         WHERE o.tenant = %s
           AND o.status = '已完成'
           AND o.pay_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
         GROUP BY o.shop_number, et_date, i.spu_name
         HAVING quantity > 0
         ORDER BY o.shop_number, et_date, quantity DESC
         LIMIT 500000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())
