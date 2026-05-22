"""Per-half-hour efficiency timings + sales counts.

Definitions (confirmed):
  - 单均接单响应时长 = SUM(accept_time - pay_time) / completed_orders
  - 平均等效制作时长 = SUM(finish_time - accept_time) / equiv_products_completed
  - 效能时长 = sum of the two

Bucketing: round pay_time (US/Eastern) down to the nearest 30 minutes.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect
from .orders import FRESH_CATEGORIES


def fetch_half_hour_efficiency(retain_days: int = 3) -> list[dict[str, Any]]:
    """Per (shop_no, ET-date, slot) timing rollups. Retain ~3 days to keep payload lean."""
    sql = """
        SELECT
            o.shop_number                                                       AS shop_no,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern'))                   AS et_date,
            DATE_FORMAT(
              FROM_UNIXTIME(
                FLOOR(UNIX_TIMESTAMP(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern')) / 1800) * 1800
              ),
              '%H:%i'
            )                                                                   AS slot,
            COUNT(*)                                                            AS order_count,
            SUM(TIMESTAMPDIFF(SECOND, o.pay_time, m.accept_time))               AS accept_total_seconds,
            SUM(TIMESTAMPDIFF(SECOND, m.accept_time, m.finish_time))            AS make_total_seconds
          FROM luckyus_sales_order.t_order o
          JOIN luckyus_sales_order.t_order_make m ON m.order_id = o.id
         WHERE o.tenant = %s
           AND o.status = '已完成'
           AND o.pay_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
           AND m.accept_time IS NOT NULL
           AND m.finish_time IS NOT NULL
         GROUP BY o.shop_number, et_date, slot
         ORDER BY o.shop_number, et_date, slot
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def fetch_half_hour_sales(retain_days: int = 3) -> list[dict[str, Any]]:
    """Per (shop_no, ET-date, slot) sales rollups — channel + category split."""
    fresh_in = ", ".join(["%s"] * len(FRESH_CATEGORIES))
    sql = f"""
        SELECT
            o.shop_number                                                       AS shop_no,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern'))                   AS et_date,
            DATE_FORMAT(
              FROM_UNIXTIME(
                FLOOR(UNIX_TIMESTAMP(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern')) / 1800) * 1800
              ),
              '%H:%i'
            )                                                                   AS slot,
            SUM(CASE WHEN o.channel IN (1, 2, 3)  THEN 1 ELSE 0 END)            AS pickup_count,
            SUM(CASE WHEN o.channel IN (8, 9, 10) THEN 1 ELSE 0 END)            AS delivery_count,
            SUM(CASE WHEN i.one_category_name IN ({fresh_in})           THEN i.qty ELSE 0 END) AS fresh_made_count,
            SUM(CASE WHEN i.one_category_name NOT IN ({fresh_in}) OR i.one_category_name IS NULL THEN i.qty ELSE 0 END) AS purchased_count
          FROM luckyus_sales_order.t_order o
          JOIN luckyus_sales_order.t_order_item i ON i.order_id = o.id
         WHERE o.tenant = %s
           AND o.status = '已完成'
           AND o.pay_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
         GROUP BY o.shop_number, et_date, slot
         ORDER BY o.shop_number, et_date, slot
         LIMIT 100000
    """
    assert_read_only(sql)
    params = [*FRESH_CATEGORIES, *FRESH_CATEGORIES, TENANT, retain_days]
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
