"""Discover tables for pending metrics: QC audits, labor/attendance, customer ratings,
BOM / theoretical cost.

Output: pipeline/schema_map.json — keyed by concept, each entry lists candidate
(database, table) pairs found via case-insensitive LIKE searches.

Run independently of the refresh:
    MYSQL_SECRET_NAME=<secret> python3 -m pipeline.schema_probe

Never blocks the build. If the probe fails (network down, gateway unreachable),
it writes an empty map and exits 0 — pending metrics simply stay pending.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from .config.settings import assert_read_only, connect

OUTPUT = Path(__file__).resolve().parent / "schema_map.json"

# Concept → list of LIKE patterns to match against table_name.
PROBE_PATTERNS: dict[str, list[str]] = {
    "qc_audit":  ["%qc%", "%quality%", "%inspect%", "%audit%", "%稽核%"],
    "labor":     ["%attend%", "%shift%", "%schedule%", "%labor%", "%考勤%", "%排班%"],
    "rating":    ["%rating%", "%review%", "%comment%", "%evaluate%", "%评价%"],
    "bom_cost":  ["%bom%", "%recipe%", "%formula%", "%spec_cost%", "%cost%"],
}

# Restrict probing to luckyus_* schemas to keep query scope tight.
SCHEMA_FILTERS = ["luckyus_%"]


def _search(cur, schema_like: str, name_like: str) -> Iterable[dict]:
    sql = """
        SELECT table_schema, table_name, engine, table_rows
          FROM information_schema.tables
         WHERE table_schema LIKE %s
           AND table_name   LIKE %s
         ORDER BY table_schema, table_name
         LIMIT 200
    """
    assert_read_only(sql)
    cur.execute(sql, (schema_like, name_like))
    return cur.fetchall()


def main() -> None:
    result: dict[str, dict] = {concept: {"patterns": pats, "matches": []} for concept, pats in PROBE_PATTERNS.items()}

    try:
        with connect("information_schema") as conn:
            with conn.cursor() as cur:
                for concept, patterns in PROBE_PATTERNS.items():
                    seen: set[tuple[str, str]] = set()
                    for schema in SCHEMA_FILTERS:
                        for p in patterns:
                            for row in _search(cur, schema, p):
                                key = (row["table_schema"], row["table_name"])
                                if key in seen:
                                    continue
                                seen.add(key)
                                result[concept]["matches"].append({
                                    "database": row["table_schema"],
                                    "table": row["table_name"],
                                    "engine": row.get("engine"),
                                    "approx_rows": row.get("table_rows"),
                                    "matched_pattern": p,
                                })
    except Exception as exc:  # noqa: BLE001
        # Probe is best-effort; never block the build.
        result["_error"] = {"message": str(exc)}

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {k: len(v["matches"]) for k, v in result.items() if k != "_error"}
    print(f"[schema_probe] wrote {OUTPUT}: {counts}")


if __name__ == "__main__":
    main()
