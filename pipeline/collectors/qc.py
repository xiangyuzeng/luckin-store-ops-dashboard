"""Quality-control audit collector for qcPassRate + qcAvgScore.

Source: luckyus_opqualitycontrol.t_shopcheck_report — one row per audit.
  - dept_id matches the production shop_id roster (verified 2026-05-28).
  - score is smallint 0-100; ≥80 counts as pass per the registered formula.
  - status enum (10=已完成, 40=整改中) both carry valid scored audits; both
    are included. 4 status=40 rows contain anomalous negative scores
    (e.g. -198) presumably from data-entry errors — filtered via
    `score > 0 AND score <= 100`.

Data is SPARSE: ~185 LKUS reports across 9 months ≈ 1/store/month. The
emitted per-day rows will be null for most (shop, day) cells. The frontend
aggregates {num,den} pairs across the user's selected window via
aggregateRatio, so WTD / MTD / QTD figures remain meaningful.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_daily_qc(retain_days: int = 90) -> list[dict[str, Any]]:
    """Per (shop_id, check_date) audit aggregates."""
    sql = """
        SELECT
            dept_id    AS shop_id,
            check_date AS et_date,
            COUNT(*)   AS report_count,
            SUM(score) AS score_sum,
            SUM(CASE WHEN score >= 80 THEN 1 ELSE 0 END) AS pass_count
          FROM luckyus_opqualitycontrol.t_shopcheck_report
         WHERE tenant = %s
           AND check_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
           AND score > 0
           AND score <= 100
         GROUP BY dept_id, check_date
         ORDER BY dept_id, check_date
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_opqualitycontrol") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())
