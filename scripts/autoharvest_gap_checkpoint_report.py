#!/usr/bin/env python3
"""Write a target-gap autoharvest checkpoint report."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists
from lib.autoharvest_gap import gap_count


def make_report(db_path: Path, run_id: str, out_path: Path, target: int = 2000) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        target_count, target_weight = gap_count(conn, run_id) if table_exists(conn, "provisional_records") else (0, 0.0)
        raw = conn.execute("SELECT COUNT(*) FROM provisional_records WHERE run_id=?", (run_id,)).fetchone()[0] if table_exists(conn, "provisional_records") else 0
        auxiliary = raw - target_count
        candidates = conn.execute("SELECT COUNT(*) FROM harvest_candidates WHERE run_id=?", (run_id,)).fetchone()[0] if table_exists(conn, "harvest_candidates") else 0
        pages = conn.execute("SELECT COUNT(*) FROM harvest_pages WHERE run_id=?", (run_id,)).fetchone()[0] if table_exists(conn, "harvest_pages") else 0
        temporal = Counter(row[0] or "none" for row in conn.execute("SELECT temporal_evidence_type FROM provisional_records WHERE run_id=? AND target_gap_eligible=1", (run_id,))) if table_exists(conn, "provisional_records") else Counter()
        years = Counter(row[0] or "unknown" for row in conn.execute("SELECT COALESCE(source_publication_year, narrative_year, coverage_start_year) FROM provisional_records WHERE run_id=? AND target_gap_eligible=1", (run_id,))) if table_exists(conn, "provisional_records") else Counter()
        states = Counter(row[0] or "unknown" for row in conn.execute("SELECT target_state FROM provisional_records WHERE run_id=? AND target_gap_eligible=1", (run_id,))) if table_exists(conn, "provisional_records") else Counter()
        routes = [dict(row) for row in conn.execute(
            """
            SELECT route_id, source_name, COUNT(*) AS target_records, SUM(target_effective_weight) AS target_weight
            FROM provisional_records
            WHERE run_id=? AND target_gap_eligible=1
            GROUP BY route_id, source_name
            ORDER BY target_weight DESC
            LIMIT 20
            """,
            (run_id,),
        )] if table_exists(conn, "provisional_records") else []
        aux_routes = [dict(row) for row in conn.execute(
            """
            SELECT route_family, source_name, COUNT(*) AS auxiliary_records
            FROM provisional_records
            WHERE run_id=? AND COALESCE(target_gap_eligible,0)=0
            GROUP BY route_family, source_name
            ORDER BY auxiliary_records DESC
            LIMIT 20
            """,
            (run_id,),
        )] if table_exists(conn, "provisional_records") else []
        paused = [dict(row) for row in conn.execute("SELECT route_id, source_name, notes FROM harvest_frontier WHERE run_id=? AND status='paused' LIMIT 20", (run_id,))] if table_exists(conn, "harvest_frontier") else []
    late = sum(count for year, count in years.items() if isinstance(year, int) and 1955 <= year <= 1976)
    priority = sum(states.get(state, 0) for state in {"WA", "SA", "NT", "TAS", "ACT"})
    lines = [
        "# Gap Autoharvest Checkpoint",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Target-gap effective records / target: `{round(target_weight, 2)} / {target}`",
        f"- Target-gap raw records: `{target_count}`",
        f"- Auxiliary provisional records: `{auxiliary}`",
        f"- Raw candidates: `{candidates}`",
        f"- Pages fetched: `{pages}`",
        f"- Target conversion rate: `{round((target_count / candidates * 100) if candidates else 0, 2)}%`",
        f"- 1955-1976 target share: `{round((late / target_count * 100) if target_count else 0, 2)}%`",
        f"- WA/SA/NT/TAS/ACT target share: `{round((priority / target_count * 100) if target_count else 0, 2)}%`",
        "",
        "## Temporal Evidence Types",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in temporal.most_common()] or ["- None yet"])
    lines.extend(["", "## Top Target-Yield Routes"])
    lines.extend([f"- `{row.get('route_id')}` {row.get('source_name') or ''}: {row.get('target_records')} records / weight {round(float(row.get('target_weight') or 0), 2)}" for row in routes] or ["- None yet"])
    lines.extend(["", "## Auxiliary-Only Producers"])
    lines.extend([f"- `{row.get('source_name')}` ({row.get('route_family')}): {row.get('auxiliary_records')}" for row in aux_routes] or ["- None yet"])
    lines.extend(["", "## Paused Routes"])
    lines.extend([f"- `{row.get('route_id')}` {row.get('source_name') or ''}" for row in paused] or ["- None"])
    lines.extend(["", "## Next Automatic Action", "Continue only through target-gap yielding routes; auxiliary growth does not count."])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"target_count": target_count, "target_weight": target_weight, "auxiliary": auxiliary, "pages": pages, "candidates": candidates, "out": str(out_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--target-gap-effective-records", type=int, default=2000)
    args = parser.parse_args()
    summary = make_report(Path(args.db), args.run_id, Path(args.out), args.target_gap_effective_records)
    print(f"Wrote gap checkpoint report: {args.out}")
    print(summary)


if __name__ == "__main__":
    main()
