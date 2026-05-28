"""BOM + unit-cost collectors for materialLossRate.

Two functions:
  - fetch_bom_avg(): per (spu_code, material_mid) average material consumption
    qty from luckyus_scm_commodity.t_formula_average. The "average" table is
    the system's pre-aggregated view that already smooths combo / option
    variants of each SPU, so we don't have to enumerate config_type=1/2/3
    rows in t_formula_spu by hand. Manual overrides win when set.

  - fetch_goods_unit_costs(): per goods_mid weighted-average unit cost from
    luckyus_scm_purchase.t_goods_spec_cost_detail. The cost table is per
    receipt (purchase order line), keyed by spec_mid like "GS07441-01".
    BOM material_mid is at the goods level ("GS07441" — no -NN suffix), so
    we collapse all spec variants by stripping the suffix via
    SUBSTRING_INDEX(spec_mid, '-', 1) and weight by receive_count to get
    a single goods-level unit cost per material.

The cross-db join (commodity × purchase × sales × shopstock) is done in
Python in frontend_formatter — each collector returns the smallest useful
shape and the formatter assembles the per (shop_id, et_date) loss-rate
fractions.

Trade-offs documented in this file rather than the formatter so future
edits don't drift from the data assumptions:
  - Collapsing spec → goods loses precision when one goods_mid has very
    different spec costs (e.g. 12oz vs 24oz of the same syrup). Picking a
    single spec also has bias. Weighted average across all live specs is
    the least-bad option without per-SPU spec mapping.
  - 365-day window for cost — long enough that low-frequency receipts
    still surface a price, short enough that retired specs don't pollute.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_bom_avg() -> list[dict[str, Any]]:
    """Per (spu_code, material_mid) avg material consumption qty for LKUS."""
    sql = """
        SELECT
            spu_code,
            material_mid,
            COALESCE(manual_avg_need_number, avg_need_number) AS need_qty
          FROM luckyus_scm_commodity.t_formula_average
         WHERE tenant = %s
           AND COALESCE(manual_avg_need_number, avg_need_number) > 0
         ORDER BY spu_code, material_mid
         LIMIT 100000
    """
    assert_read_only(sql)
    with connect("luckyus_scm_commodity") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT,))
            return list(cur.fetchall())


def fetch_goods_unit_costs(window_days: int = 365) -> list[dict[str, Any]]:
    """Per goods_mid weighted-avg unit cost across recent receipts.

    goods_mid is derived as SUBSTRING_INDEX(spec_mid, '-', 1) — i.e. the
    prefix before the first dash. BOM material_mid uses the same prefix
    convention, so this is the join key. Weighted by receive_count so
    high-volume specs dominate the average.
    """
    sql = """
        SELECT
            SUBSTRING_INDEX(spec_mid, '-', 1) AS goods_mid,
            SUM(inbound_amount * receive_count) / NULLIF(SUM(receive_count), 0) AS unit_cost,
            SUM(receive_count) AS total_received,
            MAX(receive_time) AS latest_receipt
          FROM luckyus_scm_purchase.t_goods_spec_cost_detail
         WHERE tenant = %s
           AND receive_time >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
           AND receive_count > 0
           AND inbound_amount > 0
         GROUP BY goods_mid
        HAVING unit_cost > 0
         ORDER BY goods_mid
         LIMIT 10000
    """
    assert_read_only(sql)
    with connect("luckyus_scm_purchase") as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (TENANT, window_days))
            return list(cur.fetchall())
