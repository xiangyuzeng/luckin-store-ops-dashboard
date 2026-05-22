"""Store directory + operating-today flag.

`operating_today` = had >=1 completed order in the last 24h ET (locked decision).
This is computed directly from t_order so the dropdown reflects real activity,
not just the t_shop_info.status flag.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect


def fetch_store_directory() -> list[dict[str, Any]]:
    sql_master = """
        SELECT shop_number, shop_name, status
          FROM luckyus_opshop.t_shop_info
         WHERE tenant = %s
           AND status = 1
         LIMIT 500
    """
    assert_read_only(sql_master)

    sql_active = """
        SELECT DISTINCT shop_number
          FROM luckyus_sales_order.t_order
         WHERE tenant = %s
           AND status = '已完成'
           AND pay_time >= UTC_TIMESTAMP() - INTERVAL 24 HOUR
         LIMIT 5000
    """
    assert_read_only(sql_active)

    with connect("luckyus_opshop") as conn:
        with conn.cursor() as cur:
            cur.execute(sql_master, (TENANT,))
            master = cur.fetchall()

    with connect("luckyus_sales_order") as conn:
        with conn.cursor() as cur:
            cur.execute(sql_active, (TENANT,))
            active_rows = cur.fetchall()
    active = {r["shop_number"] for r in active_rows}

    out: list[dict[str, Any]] = []
    for r in master:
        out.append({
            "shop_no": r["shop_number"],
            "shop_name": r["shop_name"],
            "operating_today": r["shop_number"] in active,
        })
    return out
