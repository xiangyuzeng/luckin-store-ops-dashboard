"""Tests for the two changes that came out of the 2026-09-01 slow-query audit.

LCNA-DBA-SQL-2026-0901-B found this pipeline responsible for the largest group
of L0 slow SQL on aws-luckyus-salesorder-rw: 366.5 s of DB time over 7 days,
40.7% of that batch. Two causes, both fixed here, both pinned below.

  1. fetch_spu_daily and fetch_spu_code_daily issued SQL that differed only in
     one column and scanned the same 2.09M rows twice a night. They are now one
     scan, collapsed in Python — so the collapse has to be exactly what the two
     queries used to return, HAVING qty > 0 included.

  2. Every run re-queried 90 days, which made the optimizer abandon
     idx_pay_time and full-scan t_order. Runs are now incremental and spliced
     into the previous payload — so the splice has to keep history intact
     without resurrecting days that legitimately changed.

Run from the repo root:  python -m unittest discover -s pipeline/tests
"""

import unittest

from pipeline.collectors.orders import aggregate_spu_rows
from pipeline.frontend_formatter import _splice_rows


def _row(shop, day, code, name, qty):
    return {"shop_id": shop, "et_date": day, "spu_code": code,
            "spu_name": name, "qty": qty}


class AggregateSpuRows(unittest.TestCase):
    def test_projects_onto_each_column(self):
        rows = [
            _row(1, "2026-08-30", "SPU001", "Iced Coconut Latte", 35),
            _row(1, "2026-08-30", "SPU002", "Americano", 12),
        ]
        by_name = aggregate_spu_rows(rows, "spu_name")
        by_code = aggregate_spu_rows(rows, "spu_code")
        self.assertEqual([r["spu_name"] for r in by_name],
                         ["Americano", "Iced Coconut Latte"])
        self.assertEqual(sum(r["qty"] for r in by_name), 47)
        self.assertEqual(sum(r["qty"] for r in by_code), 47)

    def test_one_name_under_two_codes_sums_on_the_name_side(self):
        # The reason the merged query groups by both columns: a rename or a
        # re-coded SKU splits into two rows, and the TOP-N display path has to
        # see them as one product.
        rows = [
            _row(1, "2026-08-30", "SPU001", "Americano", 10),
            _row(1, "2026-08-30", "SPU009", "Americano", 4),
        ]
        by_name = aggregate_spu_rows(rows, "spu_name")
        self.assertEqual(len(by_name), 1)
        self.assertEqual(by_name[0]["qty"], 14)
        self.assertEqual(len(aggregate_spu_rows(rows, "spu_code")), 2)

    def test_a_null_key_drops_only_that_projection(self):
        # The old pair filtered spu_name IS NOT NULL / spu_code IS NOT NULL
        # separately; the merged query keeps a row if either is present.
        rows = [_row(1, "2026-08-30", "SPU001", None, 7)]
        self.assertEqual(aggregate_spu_rows(rows, "spu_name"), [])
        self.assertEqual(len(aggregate_spu_rows(rows, "spu_code")), 1)

    def test_non_positive_totals_are_dropped_like_the_old_having(self):
        rows = [
            _row(1, "2026-08-30", "SPU001", "Refunded Item", 3),
            _row(1, "2026-08-30", "SPU002", "Refunded Item", -3),
        ]
        self.assertEqual(aggregate_spu_rows(rows, "spu_name"), [])


class SpliceRows(unittest.TestCase):
    """fresh_from is the first day this run re-collected in full."""

    def setUp(self):
        self.prev = [
            {"shop_no": "US00001", "date": "2026-05-01", "order_count": 1},   # aged out
            {"shop_no": "US00001", "date": "2026-08-20", "order_count": 100},
            {"shop_no": "US00001", "date": "2026-08-30", "order_count": 200},  # stale
        ]
        self.fresh = [
            {"shop_no": "US00001", "date": "2026-08-30", "order_count": 205},
            {"shop_no": "US00001", "date": "2026-08-31", "order_count": 190},
        ]

    def test_fresh_days_win_and_older_days_carry_over(self):
        out = _splice_rows(self.prev, self.fresh,
                           fresh_from="2026-08-30", retain_from="2026-06-01")
        by_date = {r["date"]: r["order_count"] for r in out}
        self.assertEqual(by_date["2026-08-20"], 100)   # carried over
        self.assertEqual(by_date["2026-08-30"], 205)   # re-collected, not 200
        self.assertEqual(by_date["2026-08-31"], 190)   # new day
        self.assertNotIn("2026-05-01", by_date)        # outside retention

    def test_a_day_that_lost_its_rows_does_not_come_back(self):
        # A store that stopped operating, or an order set that was cancelled:
        # inside the re-collected window, absence is the answer.
        out = _splice_rows(
            self.prev,
            [{"shop_no": "US00001", "date": "2026-08-31", "order_count": 190}],
            fresh_from="2026-08-30", retain_from="2026-06-01",
        )
        self.assertEqual([r["date"] for r in out], ["2026-08-20", "2026-08-31"])

    def test_output_is_ordered_by_date(self):
        out = _splice_rows(self.prev, self.fresh,
                           fresh_from="2026-08-30", retain_from="2026-06-01")
        self.assertEqual([r["date"] for r in out], sorted(r["date"] for r in out))

    def test_an_empty_previous_payload_yields_just_the_fresh_window(self):
        out = _splice_rows([], self.fresh,
                           fresh_from="2026-08-30", retain_from="2026-06-01")
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
