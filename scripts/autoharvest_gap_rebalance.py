#!/usr/bin/env python3
"""Rebalance gap autoharvest frontier by target-gap yield, not raw growth."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso


def rebalance(db_path: Path, config_path: Path, run_id: str, out_path: Path) -> dict[str, int]:
    boosted = paused_aux = paused_noise = paused_dupe = paused_zero_target_expansion = 0
    with sqlite3.connect(db_path) as conn:
        pages = conn.execute("SELECT COUNT(*) FROM harvest_pages WHERE run_id=?", (run_id,)).fetchone()[0]
        target_rows = conn.execute("SELECT COUNT(*) FROM provisional_records WHERE run_id=? AND target_gap_eligible=1", (run_id,)).fetchone()[0]
        conn.execute(
            """
            UPDATE harvest_frontier
            SET priority_score=priority_score+60
            WHERE run_id=? AND status='queued' AND route_id IN (
                SELECT route_id FROM provisional_records
                WHERE run_id=? AND target_gap_eligible=1
                GROUP BY route_id
                HAVING COUNT(*) > 0
            )
            """,
            (run_id, run_id),
        )
        boosted = conn.total_changes
        conn.execute(
            """
            UPDATE harvest_frontier
            SET status='paused', notes=COALESCE(notes,'') || ';paused_auxiliary_only_gap_rebalance'
            WHERE run_id=? AND status='queued' AND route_id IN (
                SELECT route_id FROM provisional_records
                WHERE run_id=?
                GROUP BY route_id
                HAVING SUM(CASE WHEN target_gap_eligible=1 THEN 1 ELSE 0 END)=0 AND COUNT(*) >= 20
            )
            """,
            (run_id, run_id),
        )
        paused_aux = conn.total_changes - boosted
        conn.execute(
            """
            UPDATE harvest_frontier
            SET status='paused', notes=COALESCE(notes,'') || ';paused_noise_gap_rebalance'
            WHERE run_id=? AND status='queued' AND route_id IN (
                SELECT route_id FROM harvest_candidates
                WHERE run_id=?
                GROUP BY route_id
                HAVING SUM(CASE WHEN gate_reasons_json LIKE '%noise%' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) > 0.8
            )
            """,
            (run_id, run_id),
        )
        paused_noise = conn.total_changes - boosted - paused_aux
        conn.execute(
            """
            UPDATE harvest_frontier
            SET status='paused', notes=COALESCE(notes,'') || ';paused_duplicate_gap_rebalance'
            WHERE run_id=? AND status='queued' AND route_id IN (
                SELECT route_id FROM harvest_candidates
                WHERE run_id=?
                GROUP BY route_id
                HAVING SUM(CASE WHEN duplicate_status NOT IN ('unique','probably_unique','unique_or_probably_unique','unchecked','') THEN 1 ELSE 0 END) * 1.0 / COUNT(*) > 0.85
            )
            """,
            (run_id, run_id),
        )
        paused_dupe = conn.total_changes - boosted - paused_aux - paused_noise
        if pages >= 50 and target_rows == 0:
            conn.execute(
                """
                UPDATE harvest_frontier
                SET status='paused', notes=COALESCE(notes,'') || ';paused_zero_target_discovered_expansion'
                WHERE run_id=? AND status='queued' AND url_type='discovered_route'
                """,
                (run_id,),
            )
            paused_zero_target_expansion = conn.total_changes - boosted - paused_aux - paused_noise - paused_dupe
        conn.commit()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(
            [
                "# Gap Frontier Rebalance",
                "",
                f"- Generated: `{now_iso()}`",
                f"- Run ID: `{run_id}`",
                f"- Target-gap yielding queued rows boosted: `{boosted}`",
                f"- Auxiliary-only queued rows paused: `{paused_aux}`",
                f"- Noisy queued rows paused: `{paused_noise}`",
                f"- Duplicate-heavy queued rows paused: `{paused_dupe}`",
                f"- Zero-target discovered-route expansion rows paused: `{paused_zero_target_expansion}`",
                "- Raw auxiliary growth counted as target: `no`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"boosted": boosted, "paused_auxiliary": paused_aux, "paused_noise": paused_noise, "paused_duplicate": paused_dupe, "paused_zero_target_expansion": paused_zero_target_expansion}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = rebalance(Path(args.db), Path(args.config), args.run_id, Path(args.out))
    print(f"Wrote gap rebalance report: {args.out}")
    print(summary)


if __name__ == "__main__":
    main()
