"""Per-half-hour rollups — sales (deltas of running totals) + efficiency timings.

The store_fact table stores half-hourly *running totals* within the day, so the
per-half-hour SALES counts come from computing slot-to-slot deltas of those
totals (the previous half-hour's value is subtracted from the current). The
23:30 bucket resets to 0 and is filtered out.

Efficiency timings (single-order accept response, equivalent make duration)
come directly from t_order ⋈ t_order_make grouped by (shop, ET-date, half-hour
slot).
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_half_hour_running_totals(retain_days: int = 3) -> list[dict[str, Any]]:
    """Half-hourly running totals from t_order_store_fact (cycle_type=3).

    The aggregator turns these into per-slot SALES deltas. Keep retention small
    (default 3 days) because the dashboard's interval tables only need a recent
    window and per-half-hour data is the bulk of payload size.
    """
    sql = """
        SELECT
            shop_id,
            local_begin_date,
            total_order_quantity,
            pickup_order_quantity,
            delivery_order_quantity,
            self_quantity,
            purchase_quantity,
            make_seconds
          FROM luckyus_sales_order.t_order_store_fact
         WHERE tenant = %s
           AND cycle_type = 3
           AND local_begin_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
         ORDER BY shop_id, local_begin_date
         LIMIT 50000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def fetch_half_hour_timing(retain_days: int = 3) -> list[dict[str, Any]]:
    """Per (shop_id, ET-date, half-hour slot) timing rollups.

    Note: the literal % inside DATE_FORMAT's pattern is doubled (%%) because
    pymysql renders parameterized queries via Python %-formatting; an
    un-escaped %H would be read as a format placeholder.
    """
    sql = """
        SELECT
            o.shop_id,
            DATE(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern')) AS et_date,
            DATE_FORMAT(
              FROM_UNIXTIME(
                FLOOR(UNIX_TIMESTAMP(CONVERT_TZ(o.pay_time, 'UTC', 'US/Eastern')) / 1800) * 1800
              ),
              '%%H:%%i'
            )                                                 AS slot,
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
         GROUP BY o.shop_id, et_date, slot
         ORDER BY o.shop_id, et_date, slot
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())
