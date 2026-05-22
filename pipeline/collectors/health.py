"""Health-counter cross-check from t_collect_*_inter.

These rollups exist independently of t_order and serve as a sanity check on the
per-day order counts. If a large divergence is detected, the formatter logs a
warning but still ships the payload — we don't block on it.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_open_store_counts(retain_days: int = 40) -> list[dict[str, Any]]:
    sql = """
        SELECT
            DATE(CONVERT_TZ(stat_time, 'UTC', 'US/Eastern')) AS et_date,
            metric_value                                     AS value
          FROM luckyus_iluckyhealth.t_collect_shop_inter
         WHERE tenant = %s
           AND metric_name = 'tenant_shop_now_opening'
           AND stat_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
         ORDER BY stat_time
         LIMIT 20000
    """
    assert_read_only(sql)
    with connect("luckyus_iluckyhealth") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def fetch_tenant_order_counters(retain_days: int = 40) -> list[dict[str, Any]]:
    sql = """
        SELECT
            DATE(CONVERT_TZ(stat_time, 'UTC', 'US/Eastern')) AS et_date,
            metric_name,
            metric_value                                     AS value
          FROM luckyus_iluckyhealth.t_collect_order_tenant_inter
         WHERE tenant = %s
           AND metric_name IN (
             'order_all_done_tenant',
             'order_all_pay_tenant',
             'order_all_cancel_tenant',
             'order_all_create_tenant'
           )
           AND stat_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
         ORDER BY stat_time
         LIMIT 50000
    """
    assert_read_only(sql)
    with connect("luckyus_iluckyhealth") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())
