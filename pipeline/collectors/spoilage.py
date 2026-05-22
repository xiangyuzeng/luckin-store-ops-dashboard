"""Spoilage / material-loss collector.

Source confirmed: t_shop_spec_stock_change_record with specific_reason_code='015'
is the actual-loss numerator. The theoretical denominator (BOM x sales x cost) is
NOT yet mapped — schema_probe.py searches for it. Until found, the formatter
emits material_loss_rate=null so the UI shows '数据源待接入'.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_daily_spoilage(retain_days: int = 40) -> list[dict[str, Any]]:
    sql = """
        SELECT
            r.shop_id,
            DATE(CONVERT_TZ(r.operated_time, 'UTC', 'US/Eastern')) AS et_date,
            SUM(ABS(r.total_adjust_num))                           AS adjust_units
          FROM luckyus_scm_shopstock.t_shop_spec_stock_change_record r
         WHERE r.tenant = %s
           AND r.specific_reason_code = '015'
           AND r.operated_time >= UTC_TIMESTAMP() - INTERVAL %s DAY
         GROUP BY r.shop_id, et_date
         ORDER BY r.shop_id, et_date
         LIMIT 50000
    """
    assert_read_only(sql)
    with connect("luckyus_scm_shopstock") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())
