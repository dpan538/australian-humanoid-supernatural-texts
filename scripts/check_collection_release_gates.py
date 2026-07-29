#!/usr/bin/env python3
"""Check latest collection-expansion release gate results."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import table_exists


def latest_gate_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
        SELECT gate_run_id
        FROM release_gate_results
        GROUP BY gate_run_id
        ORDER BY MAX(created_at) DESC
        LIMIT 1
        """
    ).fetchone()
    return str(row["gate_run_id"]) if row else None


def check_gates(db_path: Path) -> tuple[int, list[sqlite3.Row]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "release_gate_results"):
            raise RuntimeError("release_gate_results table is missing. Run audit_collection_balance.py first.")
        run_id = latest_gate_run_id(conn)
        if not run_id:
            raise RuntimeError("No release gate results found. Run audit_collection_balance.py first.")
        rows = conn.execute(
            """
            SELECT * FROM release_gate_results
            WHERE gate_run_id = ?
            ORDER BY
              CASE gate_status WHEN 'FAIL' THEN 0 WHEN 'WARN' THEN 1 ELSE 2 END,
              gate_name
            """,
            (run_id,),
        ).fetchall()
    return (1 if any(row["gate_status"] == "FAIL" for row in rows) else 0, rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--targets", help="accepted for Makefile symmetry; gates already stored by audit")
    args = parser.parse_args()

    code, rows = check_gates(Path(args.db))
    counts = Counter(row["gate_status"] for row in rows)
    print("Collection release gates: " + ", ".join(f"{status}={counts[status]}" for status in sorted(counts)))
    for row in rows:
        if row["gate_status"] in {"FAIL", "WARN"}:
            print(f"{row['gate_status']}: {row['gate_name']} observed={row['observed_value']} threshold={row['threshold_value']}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
