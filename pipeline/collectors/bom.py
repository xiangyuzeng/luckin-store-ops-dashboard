"""BOM + unit-cost collectors for materialLossRate.

Two functions:
  - fetch_bom_avg(): per (spu_code, material_mid) average material consumption
    qty from luckyus_scm_commodity.t_formula_average. The "average" table is
    the system's pre-aggregated view that already smooths combo / option
    variants of each SPU, so we don't have to enumerate config_type=1/2/3
    rows in t_formula_spu by hand. Manual overrides win when set.

  - fetch_goods_unit_costs(): per goods_mid weighted-avg cost PER USE UNIT
    (matches BOM avg_need_number's unit — g, ml, cups, …). Joins
    t_goods_spec_cost_detail × t_mdm_goods_spec to apply the
    1 purchase = cg_dly_ratio × dly_use_ratio use-unit conversion. spec→goods
    collapse via SUBSTRING_INDEX so BOM material_mid (goods-level) joins
    directly. Specs without ratio info are skipped.

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
    """Per goods_mid weighted-avg cost PER USE UNIT (the same unit BOM is in).

    Three units flow through the SCM model: 采购 → 配货 → 用料. inbound_amount
    is the per-receive-unit (purchase-unit) cost; receive_count is in
    purchase units. BOM's avg_need_number is in use units (g, ml, cups, ...).
    Conversion factor: 1 purchase unit = cg_dly_ratio × dly_use_ratio use units.
    Required join: spec_mid → t_mdm_goods_spec.mid for the per-spec ratios.

    The previous version omitted the ratios and returned cost per purchase
    unit (per case). For items where 1 case = 1000 cups this over-estimated
    cost by 3 orders of magnitude — the rate stayed roughly correct because
    the same scale error hit both numerator and denominator and mostly
    cancelled in the ratio, but absolute dollar amounts on individual rows
    were unusable.

    goods_mid is derived via SUBSTRING_INDEX(spec_mid, '-', 1) (matches the
    BOM material_mid convention). Specs missing ratio info are skipped to
    avoid polluting the weighted average with a wrong scale.
    """
    sql = """
        SELECT
            SUBSTRING_INDEX(c.spec_mid, '-', 1) AS goods_mid,
            SUM(c.inbound_amount * c.receive_count) /
              NULLIF(SUM(c.receive_count * s.cg_dly_ratio * s.dly_use_ratio), 0) AS unit_cost,
            SUM(c.receive_count) AS total_received,
            MAX(c.receive_time) AS latest_receipt
          FROM luckyus_scm_purchase.t_goods_spec_cost_detail c
          JOIN luckyus_scm_purchase.t_mdm_goods_spec s
            ON s.mid = c.spec_mid AND s.tenant = c.tenant
         WHERE c.tenant = %s
           AND c.receive_time >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
           AND c.receive_count > 0
           AND c.inbound_amount > 0
           AND s.cg_dly_ratio > 0
           AND s.dly_use_ratio > 0
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
