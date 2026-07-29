#!/usr/bin/env python3
"""Write a milestone audit packet for structured endpoint target-gap records."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from migrate_structured_endpoint_harvest_v1 import migrate


def write_csv(path: Path, records: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})


def all_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def audit(db_path: Path, run_id: str, target: int, out_dir: Path) -> dict[str, Any]:
    migrate(db_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        target_rows = all_rows(conn, "SELECT * FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=1 ORDER BY target_gap_score DESC", (run_id,))
        near_rows = all_rows(conn, "SELECT * FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=0 AND (controlled_term_hits NOT NULL AND controlled_term_hits NOT IN ('[]','')) LIMIT 500", (run_id,))
        access_rows = all_rows(conn, "SELECT * FROM noauth_endpoint_records WHERE run_id=? AND source_tier='D' LIMIT 500", (run_id,))
        distribution_source = all_rows(conn, "SELECT source_name, source_tier, endpoint_type, COUNT(*) AS row_count FROM noauth_endpoint_records WHERE run_id=? GROUP BY source_name, source_tier, endpoint_type ORDER BY row_count DESC", (run_id,))
        distribution_temporal = all_rows(conn, "SELECT inferred_year, COUNT(*) AS row_count, SUM(target_gap_eligible) AS target_gap_rows FROM noauth_endpoint_records WHERE run_id=? GROUP BY inferred_year ORDER BY inferred_year", (run_id,))
    common = ["endpoint_record_id", "source_name", "source_tier", "endpoint_type", "title", "date_text", "inferred_year", "item_url", "target_gap_score", "gate_reasons_json"]
    write_csv(out_dir / "target_gap_records.csv", target_rows, common)
    write_csv(out_dir / "near_misses.csv", near_rows, common)
    write_csv(out_dir / "access_decomposition_candidates.csv", access_rows, common)
    write_csv(out_dir / "source_concentration.csv", distribution_source, ["source_name", "source_tier", "endpoint_type", "row_count"])
    write_csv(out_dir / "temporal_distribution.csv", distribution_temporal, ["inferred_year", "row_count", "target_gap_rows"])
    write_csv(out_dir / "promotion_proposal.csv", target_rows, common)
    effective = len(target_rows)
    abc = sum(1 for row in target_rows if row.get("source_tier") in {"A", "B", "C"})
    abc_share = (abc / effective) if effective else 0.0
    lines = [
        "# Structured Endpoint Milestone Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Target requested: `{target}`",
        f"- Target-gap records in audit: `{effective}`",
        f"- Source tier A/B/C share: `{abc_share:.2%}`",
        f"- Near misses sampled: `{len(near_rows)}`",
        f"- D-class access decomposition candidates sampled: `{len(access_rows)}`",
        "- Promotion applied: `no`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "",
        "## Gate",
        f"- Milestone reached: `{str(effective >= target).lower()}`",
        f"- Quality acceptable for automated continuation: `{str(bool(effective and abc_share >= 0.85)).lower()}`",
    ]
    (out_dir / "milestone_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"target_gap_records": effective, "abc_share": abc_share, "near_misses": len(near_rows), "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", default="noauth_structured_endpoint_001")
    parser.add_argument("--target-effective-records", type=int, default=250)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(Path(args.db), args.run_id, args.target_effective_records, Path(args.out_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
