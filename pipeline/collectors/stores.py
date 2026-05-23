"""Store directory + operating-today flag.

`operating_today` = had >=1 completed order in the last 24h ET (locked decision).
Real schema confirms:
  - t_shop_info column is `shop_no` (NOT shop_number — this collector was wrong before).
  - t_order.status=90 means 已完成 (integer, not the string '已完成').
  - Test kitchens (US00000, US99998, US99999) carry test_flag=0 and must be
    filtered out by shop_no whitelist.
"""
from __future__ import annotations

from typing import Any

from ..config.settings import TENANT, assert_read_only, connect

# Real production shops (manually curated whitelist — test_flag is unreliable).
EXCLUDED_TEST_SHOPS = {"US00000", "US99998", "US99999"}


def fetch_store_directory() -> list[dict[str, Any]]:
    sql_master = """
        SELECT shop_no, shop_name, status, set_up_time
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
           AND status = 90
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
        shop_no = r["shop_no"]
        if shop_no in EXCLUDED_TEST_SHOPS:
            continue
        out.append({
            "shop_no": shop_no,
            "shop_name": r["shop_name"],
            "set_up_time": r.get("set_up_time"),
            "operating_today": shop_no in active,
        })
    return out
