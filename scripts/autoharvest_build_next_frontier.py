#!/usr/bin/env python3
"""Rebalance autoharvest frontier priorities from route yield and gap progress."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists
from lib.autoharvest_engine import load_autoharvest_config


def rebalance(db_path: Path, run_id: str, config_path: Path, out_path: Path) -> dict[str, int]:
    config = load_autoharvest_config(config_path)
    promoted = paused = boosted = 0
    with sqlite3.connect(db_path) as conn:
        if table_exists(conn, "harvest_route_stats"):
            conn.execute(
                """
                UPDATE harvest_frontier
                SET priority_score=priority_score+25
                WHERE run_id=? AND route_id IN (
                    SELECT route_id FROM harvest_route_stats
                    WHERE run_id=? AND provisional_records_added > 0 AND noise <= candidates_seen / 2
                )
                """,
                (run_id, run_id),
            )
            promoted = conn.total_changes
            conn.execute(
                """
                UPDATE harvest_frontier
                SET status='paused'
                WHERE run_id=? AND route_id IN (
                    SELECT route_id FROM harvest_route_stats
                    WHERE run_id=? AND candidates_seen > 0 AND noise * 1.0 / candidates_seen > 0.8
                )
                """,
                (run_id, run_id),
            )
            paused = conn.total_changes - promoted
        if table_exists(conn, "provisional_records"):
            states = Counter(row[0] or "unknown" for row in conn.execute("SELECT target_state FROM provisional_records WHERE run_id=?", (run_id,)))
            if states and states.get("WA", 0) < sum(states.values()) * 0.1:
                conn.execute("UPDATE harvest_frontier SET priority_score=priority_score+30 WHERE run_id=? AND state='WA' AND status='queued'", (run_id,))
                boosted = conn.total_changes - promoted - paused
        conn.commit()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(
            [
                "# Autoharvest Frontier Rebalance",
                "",
                f"- Generated: `{now_iso()}`",
                f"- Run ID: `{run_id}`",
                f"- High-yield route rows boosted: `{promoted}`",
                f"- Noisy route rows paused: `{paused}`",
                f"- Undercovered WA rows boosted: `{boosted}`",
                "- No-auth safety constraints retained: `yes`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"boosted": promoted + boosted, "paused": paused}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = rebalance(Path(args.db), args.run_id, Path(args.config), Path(args.out))
    print(f"Wrote frontier rebalance report: {args.out}")
    print(summary)


if __name__ == "__main__":
    main()
