#!/usr/bin/env python3
"""Build an optional top-N target-gap lead review packet."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.target_gap_leads import LEAD_FIELDS, read_leads
from migrate_target_gap_leads_v1 import migrate


def build_packet(db_path: Path, out_dir: Path, limit: int) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)
    review_rows = []
    for row in leads:
        review_rows.append(
            {
                **{field: row.get(field) for field in LEAD_FIELDS},
                "why_machine_thinks_it_matters": f"{row.get('term_signal') or 'term weak'} / {row.get('temporal_signal') or 'date weak'} / {row.get('constraint_blocker')}",
                "missing_gate": row.get("evidence_gap"),
                "exact_blocker": row.get("constraint_blocker"),
                "reviewer_yes_no": "",
            }
        )
    fields = LEAD_FIELDS + ["why_machine_thinks_it_matters", "missing_gate", "exact_blocker", "reviewer_yes_no"]
    write_csv(out_dir / "top_50_leads.csv", review_rows, fields)
    lines = ["# Tiny Review Packet", "", f"- Generated: `{now_iso()}`", f"- Rows: `{len(review_rows)}`", "- This packet is optional and is not required for lead mode."]
    (out_dir / "tiny_review_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    item_lines = ["# Top 50 Leads", ""]
    for idx, row in enumerate(review_rows, start=1):
        item_lines.extend(
            [
                f"## {idx}. {row.get('title') or 'Untitled lead'}",
                f"- Source: `{row.get('source_name')}`",
                f"- Why machine thinks it matters: {row.get('why_machine_thinks_it_matters')}",
                f"- Missing gate: `{row.get('missing_gate')}`",
                f"- Exact blocker: `{row.get('exact_blocker')}`",
                "- Reviewer yes/no:",
                "",
            ]
        )
    (out_dir / "top_50_leads.md").write_text("\n".join(item_lines), encoding="utf-8")
    return {"rows": len(review_rows), "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    print(json.dumps(build_packet(Path(args.db), Path(args.out_dir), args.limit), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
