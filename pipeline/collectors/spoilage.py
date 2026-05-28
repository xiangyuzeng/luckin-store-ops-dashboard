"""Spoilage / material-loss collector.

Source confirmed: t_shop_spec_stock_change_record with specific_reason_code='015'
is the actual-loss numerator. The theoretical denominator (BOM x sales x cost) is
NOT yet mapped — schema_probe.py searches for it. Until found, the formatter
emits material_loss_rate=null so the UI shows '数据源待接入'.

Returned rows are keyed by `shop_dept_id` (the real column name on
t_shop_spec_stock_change_record). When the BOM denominator is wired in, the
formatter will need to translate dept_id → shop_no via t_shop_info.dept_id.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_daily_spoilage(retain_days: int = 40) -> list[dict[str, Any]]:
    sql = """
        SELECT
            r.shop_dept_id,
            DATE(CONVERT_TZ(r.operated_time, 'UTC', 'US/Eastern')) AS et_date,
            SUM(ABS(r.total_adjust_num))                           AS adjust_units
          FROM luckyus_scm_shopstock.t_shop_spec_stock_change_record r
         WHERE r.tenant = %s
           AND r.specific_reason_code = '015'
           AND r.operated_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
         GROUP BY r.shop_dept_id, et_date
         ORDER BY r.shop_dept_id, et_date
         LIMIT 50000
    """
    assert_read_only(sql)
    with connect("luckyus_scm_shopstock") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())


def fetch_daily_spoilage_by_spec(retain_days: int = 90) -> list[dict[str, Any]]:
    """Per (shop_id, et_date, spec_mid) spoilage qty — for unit-cost multiplication.

    shop_dept_id == shop_id (verified 2026-05-28 against t_shop_info roster).
    spec_mid kept whole; collapsing to goods_mid happens at consumer side.
    """
    sql = """
        SELECT
            r.shop_dept_id                                         AS shop_id,
            DATE(CONVERT_TZ(r.operated_time, 'UTC', 'US/Eastern')) AS et_date,
            r.spec_mid,
            SUM(ABS(r.total_adjust_num))                           AS spoiled_qty
          FROM luckyus_scm_shopstock.t_shop_spec_stock_change_record r
         WHERE r.tenant = %s
           AND r.specific_reason_code = '015'
           AND r.operated_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
           AND r.spec_mid IS NOT NULL
         GROUP BY r.shop_dept_id, et_date, r.spec_mid
        HAVING spoiled_qty > 0
         ORDER BY r.shop_dept_id, et_date
         LIMIT 200000
    """
    assert_read_only(sql)
    with connect("luckyus_scm_shopstock") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())
