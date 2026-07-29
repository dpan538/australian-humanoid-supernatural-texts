#!/usr/bin/env python3
"""Write a compact autoharvest checkpoint report."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists


def rows(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(query, params).fetchall()


def make_report(db_path: Path, run_id: str, out_path: Path) -> dict[str, float]:
    with sqlite3.connect(db_path) as conn:
        if not table_exists(conn, "provisional_records"):
            raw = weighted = pages = candidates = 0
            prov_rows = []
        else:
            raw, weighted = conn.execute("SELECT COUNT(*), COALESCE(SUM(growth_weight),0) FROM provisional_records WHERE run_id=?", (run_id,)).fetchone()
            pages = conn.execute("SELECT COUNT(*) FROM harvest_pages WHERE run_id=?", (run_id,)).fetchone()[0]
            candidates = conn.execute("SELECT COUNT(*) FROM harvest_candidates WHERE run_id=?", (run_id,)).fetchone()[0]
            prov_rows = rows(conn, "SELECT * FROM provisional_records WHERE run_id=?", (run_id,))
        route_rows = rows(conn, "SELECT * FROM harvest_route_stats WHERE run_id=? ORDER BY yield_score DESC LIMIT 20", (run_id,)) if table_exists(conn, "harvest_route_stats") else []
        candidate_rows = rows(conn, "SELECT * FROM harvest_candidates WHERE run_id=?", (run_id,)) if table_exists(conn, "harvest_candidates") else []
    states = Counter(row["target_state"] or "unknown" for row in prov_rows)
    bands = Counter(row["time_band"] or "unknown" for row in prov_rows)
    tiers = Counter(row["source_tier"] or "unknown" for row in prov_rows)
    duplicates = sum(1 for row in candidate_rows if row["duplicate_status"] not in {"unique", "probably_unique", "unique_or_probably_unique", "unchecked"})
    noise = sum(1 for row in candidate_rows if "noise" in (row["gate_reasons_json"] or ""))
    conversion = 0 if candidates == 0 else round(raw / candidates * 100, 2)
    eta = "unknown" if raw == 0 else f"{round(max(0, 2000 - weighted) / max(weighted, 1), 2)} current-run equivalents"
    lines = [
        "# Autoharvest Checkpoint",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Effective records added / target: `{round(weighted, 2)} / 2000`",
        f"- Raw provisional records added: `{raw}`",
        f"- Weighted growth score: `{round(weighted, 2)}`",
        f"- Pages fetched: `{pages}`",
        f"- Candidates seen: `{candidates}`",
        f"- Candidate-to-provisional conversion rate: `{conversion}%`",
        f"- Duplicates: `{duplicates}`",
        f"- Noise rate: `{0 if candidates == 0 else round(noise / candidates * 100, 2)}%`",
        f"- ETA to 2,000: `{eta}`",
        "- Human action required: `no unless safety stop appears`",
        "",
        "## Route Yield Top 20",
    ]
    lines.extend([f"- `{row['route_id']}` score `{row['yield_score']}` action `{row['recommended_action']}`" for row in route_rows] or ["- None"])
    lines.extend(["", "## State Distribution"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(states.items())] or ["- None"])
    lines.extend(["", "## Time-Band Distribution"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(bands.items())] or ["- None"])
    lines.extend(["", "## Source-Tier Distribution"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(tiers.items())] or ["- None"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"raw": raw, "weighted": weighted, "pages": pages, "candidates": candidates}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = make_report(Path(args.db), args.run_id, Path(args.out))
    print(f"Wrote checkpoint report: {args.out}")
    print(summary)


if __name__ == "__main__":
    main()
