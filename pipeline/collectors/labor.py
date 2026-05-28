"""Labor-hours collector for the cup-rate KPIs (hourlyCups, perfHourlyCups).

Source: luckyus_opempefficiency.t_emp_kpi — one row per employee × attendance_date.
  - attendance_hours: total worked time (denominator for hourlyCups)
  - kpi_hours:        "绩效工时" — already excludes 会议 / 培训 / 帮带训 / 休息
                      (denominator for perfHourlyCups)

Aggregated per (shop_id, attendance_date) where attendance_dept_id == shop_id
(verified 2026-05-28: dept_ids in t_emp_kpi match the production shop_id
roster exactly — 1127/1128/1140/1141/20008…).

Negative kpi_hours rows are real — they are clawback / adjustment entries
that reverse hours previously counted. SUM is the correct net aggregation;
do NOT clamp to zero, that would double-count the reversed hours.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_daily_labor_hours(retain_days: int = 90) -> list[dict[str, Any]]:
    """Per (shop_id, ET-local date) attendance + KPI hour totals."""
    sql = """
        SELECT
            attendance_dept_id    AS shop_id,
            attendance_date       AS et_date,
            SUM(attendance_hours) AS labor_hours_total,
            SUM(kpi_hours)        AS labor_hours_productive,
            COUNT(*)              AS emp_day_count
          FROM luckyus_opempefficiency.t_emp_kpi
         WHERE tenant = %s
           AND attendance_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
         GROUP BY attendance_dept_id, attendance_date
        HAVING labor_hours_total > 0
         ORDER BY attendance_dept_id, et_date
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_opempefficiency") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, retain_days))
            return list(cur.fetchall())
