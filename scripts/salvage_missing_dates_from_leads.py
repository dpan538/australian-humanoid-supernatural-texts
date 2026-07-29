#!/usr/bin/env python3
"""Recover date signals from stored target-gap lead metadata only."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.lead_intelligence import extract_date_signal
from lib.target_gap_leads import LEAD_FIELDS, read_leads, score_lead, write_leads_csv
from migrate_target_gap_leads_v1 import migrate


def _remove_gap(gaps: str, gap: str) -> str:
    parts = [part for part in str(gaps or "").split(";") if part and part != gap]
    return ";".join(parts) or "strict_record_gate_not_met"


def _next_blocker(row: dict[str, Any], gaps: str) -> str:
    for blocker in ["robots_denied", "robots_unknown", "ethics_sensitive", "rights_unclear", "d_class_needs_original", "discovery_only_needs_evidence", "missing_term", "missing_item_url"]:
        if blocker in gaps:
            return blocker
    if row.get("constraint_blocker") != "missing_date":
        return row.get("constraint_blocker") or "strict_record_gate_not_met"
    return "strict_record_gate_not_met"


def salvage(db_path: Path, out: Path, execute: bool) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
        salvaged: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []
        still_missing: list[dict[str, Any]] = []
        for row in leads:
            missing_date = "missing_date" in str(row.get("evidence_gap") or "") or not (row.get("temporal_signal") or row.get("inferred_year"))
            if not missing_date:
                continue
            result = extract_date_signal(row)
            status = result["date_status"]
            if status.startswith("salvaged"):
                updated = dict(row)
                updated["temporal_signal"] = result["temporal_signal"]
                updated["inferred_year"] = result["inferred_year"]
                updated["coverage_start_year"] = result["coverage_start_year"]
                updated["coverage_end_year"] = result["coverage_end_year"]
                updated["evidence_gap"] = _remove_gap(str(row.get("evidence_gap") or ""), "missing_date")
                updated["constraint_blocker"] = _next_blocker(updated, updated["evidence_gap"])
                lead_score, bucket = score_lead(updated)
                updated["lead_score"] = lead_score
                updated["priority_bucket"] = bucket
                updated["date_salvage_status"] = status
                salvaged.append(updated)
                if execute:
                    conn.execute(
                        """
                        UPDATE target_gap_leads
                        SET temporal_signal=?, inferred_year=?, coverage_start_year=?, coverage_end_year=?,
                            evidence_gap=?, constraint_blocker=?, lead_score=?, priority_bucket=?, updated_at=?
                        WHERE lead_id=?
                        """,
                        (
                            updated["temporal_signal"],
                            updated["inferred_year"],
                            updated["coverage_start_year"],
                            updated["coverage_end_year"],
                            updated["evidence_gap"],
                            updated["constraint_blocker"],
                            updated["lead_score"],
                            updated["priority_bucket"],
                            now_iso(),
                            updated["lead_id"],
                        ),
                    )
            elif status == "ambiguous":
                row["date_salvage_status"] = status
                ambiguous.append(row)
            else:
                row["date_salvage_status"] = status
                still_missing.append(row)
        if execute:
            conn.commit()
    out.parent.mkdir(parents=True, exist_ok=True)
    write_leads_csv(out.parent / "date_salvaged_leads.csv", salvaged)
    write_leads_csv(out.parent / "still_missing_date_leads.csv", still_missing)
    write_leads_csv(out.parent / "date_ambiguous_leads.csv", ambiguous)
    lines = [
        "# Date Salvage Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Leads considered missing date: `{len(salvaged) + len(still_missing) + len(ambiguous)}`",
        f"- Dates salvaged: `{len(salvaged)}`",
        f"- Still missing date: `{len(still_missing)}`",
        f"- Date ambiguous: `{len(ambiguous)}`",
        "- Network fetches: `0`",
        "- Public records mutated: `no`",
        "",
        "## Salvage Method",
        "- Parsed existing titles, descriptions, URLs, source names, route families, temporal signals, and source-chain metadata only.",
        "- Ignored crawl/export/generated/query-plan/route-target year contexts.",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"dates_salvaged": len(salvaged), "still_missing_date": len(still_missing), "date_ambiguous": len(ambiguous), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(salvage(Path(args.db), Path(args.out), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
