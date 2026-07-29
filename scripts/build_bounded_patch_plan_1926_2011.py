#!/usr/bin/env python3
"""Build a bounded final 1926-2011 patch plan from existing research layers."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.final_release import PREFERRED_ROUTE_FAMILIES, PRIORITY_STATES, RELEASE_ITEM_FIELDS, band_for_year, source_is_concentrated
from migrate_research_volume_expansion_v1 import migrate as migrate_volume


def candidate_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows: list[dict[str, Any]] = []
    if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='research_volume_items'").fetchone()[0]:
        for row in conn.execute("SELECT * FROM research_volume_items WHERE inferred_year BETWEEN 1926 AND 2011"):
            layer = "metadata_only_gap" if row["layer"] == "metadata_only_lead" else ("lead_overlay" if row["layer"] == "target_gap_lead" else "source_intelligence")
            rows.append({
                "source_table": "research_volume_items",
                "source_row_id": row["item_id"],
                "source_lead_id": row["linked_row_id"],
                "patch_layer": layer,
                "title": f"{row['source_name']} {row['target_state']} {row['inferred_year']} release patch",
                "description": "Bounded release patch item from existing research-volume layer.",
                "url": "",
                "source_name": row["source_name"],
                "source_tier": row["source_tier"],
                "source_family": row["source_family"],
                "route_family": row["route_family"],
                "inferred_year": row["inferred_year"],
                "coverage_start_year": row["inferred_year"],
                "coverage_end_year": row["inferred_year"],
                "target_state": row["target_state"],
                "target_locality": row["target_locality"],
                "temporal_signal": row["temporal_signal"],
                "term_signal": row["term_signal"],
                "place_signal": row["target_locality"] or row["target_state"],
                "evidence_gap": row["evidence_gap"],
                "blocker": row["constraint_blocker"],
                "priority_score": row["priority_score"],
                "priority_bucket": row["priority_bucket"],
                "selection_reason": "existing_research_volume_item",
            })
    if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='target_gap_leads'").fetchone()[0]:
        for row in conn.execute("SELECT * FROM target_gap_leads WHERE COALESCE(inferred_year, coverage_start_year) BETWEEN 1926 AND 2011 AND duplicate_status IN ('canonical','unique','unchecked')"):
            year = row["inferred_year"] or row["coverage_start_year"]
            layer = "metadata_only_gap" if row["lead_type"] == "METADATA_ONLY_1955_1976_LEAD" else "lead_overlay"
            rows.append({
                "source_table": "target_gap_leads",
                "source_row_id": row["lead_id"],
                "source_lead_id": row["lead_id"],
                "patch_layer": layer,
                "title": row["title"],
                "description": row["description"],
                "url": row["url"],
                "source_name": row["source_name"],
                "source_tier": row["source_tier"],
                "source_family": row["source_family"],
                "route_family": row["route_family"],
                "inferred_year": year,
                "coverage_start_year": row["coverage_start_year"] or year,
                "coverage_end_year": row["coverage_end_year"] or year,
                "target_state": row["target_state"],
                "target_locality": row["target_locality"],
                "temporal_signal": row["temporal_signal"],
                "term_signal": row["term_signal"],
                "place_signal": row["place_signal"],
                "evidence_gap": row["evidence_gap"],
                "blocker": row["constraint_blocker"],
                "priority_score": row["lead_score"],
                "priority_bucket": row["priority_bucket"],
                "selection_reason": "canonical_or_unique_lead",
            })
    return rows


def score(row: dict[str, Any]) -> float:
    value = float(row.get("priority_score") or 0)
    year = int(row.get("inferred_year") or 0)
    if 1955 <= year <= 1976:
        value += 40
    elif 1926 <= year <= 2011:
        value += 20
    if row.get("target_state") in PRIORITY_STATES:
        value += 25
    if row.get("source_tier") in {"A", "B", "C"}:
        value += 20
    if row.get("route_family") in PREFERRED_ROUTE_FAMILIES:
        value += 15
    if row.get("target_locality") or row.get("place_signal"):
        value += 10
    text = " ".join(str(row.get(key) or "").lower() for key in ["evidence_gap", "blocker", "source_name", "source_family"])
    if "ethics_sensitive" in text or "sensitive" in text:
        value -= 100
    if "robots_unknown" in text:
        value -= 25
    if "discovery_only" in text or "d_class" in text:
        value -= 30
    if source_is_concentrated(row):
        value -= 20
    return value


def build(db_path: Path, coverage_dir: Path, out: Path, report: Path, max_patch_items: int, execute: bool) -> dict[str, object]:
    migrate_volume(db_path)
    with sqlite3.connect(db_path) as conn:
        candidates = candidate_rows(conn)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in sorted(candidates, key=lambda item: (-score(item), band_for_year(item.get("inferred_year")), item.get("target_state") or "")):
        reason = ""
        if "ethics_sensitive" in str(row.get("evidence_gap") or ""):
            reason = "ethics_sensitive"
        elif row.get("source_tier") not in {"A", "B", "C", "D"}:
            reason = "source_tier_not_allowed"
        key = (str(row.get("source_table")), str(row.get("source_row_id")))
        if key in seen:
            reason = reason or "duplicate_source_row"
        if reason:
            rejected.append({**row, "rejected_reason": reason})
            continue
        seen.add(key)
        selected.append(row)
        if len(selected) >= max_patch_items:
            break
    out.parent.mkdir(parents=True, exist_ok=True)
    if execute:
        write_csv(out, selected, RELEASE_ITEM_FIELDS)
        write_csv(out.parent / "patch_selection_by_year_band.csv", [{"category": k, "count": v} for k, v in Counter(band_for_year(row.get("inferred_year")) for row in selected).most_common()], ["category", "count"])
        write_csv(out.parent / "patch_selection_by_state.csv", [{"category": k, "count": v} for k, v in Counter(row.get("target_state") or "unknown" for row in selected).most_common()], ["category", "count"])
        write_csv(out.parent / "patch_selection_by_source_family.csv", [{"category": k, "count": v} for k, v in Counter(row.get("route_family") or "unknown" for row in selected).most_common()], ["category", "count"])
        write_csv(out.parent / "patch_rejected_reasons.csv", [{"category": k, "count": v} for k, v in Counter(row.get("rejected_reason") for row in rejected).most_common()], ["category", "count"])
    lines = [
        "# Bounded Patch Plan 1926-2011",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Max patch items: `{max_patch_items}`",
        f"- Selected patch items: `{len(selected)}`",
        f"- Rejected candidates: `{len(rejected)}`",
        "- Open-ended crawling: `no`",
        "- Public record autopromotion: `no`",
        "",
        "## Selection By Layer",
    ]
    lines.extend([f"- `{k}`: {v}" for k, v in Counter(row["patch_layer"] for row in selected).most_common()])
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"selected": len(selected), "rejected": len(rejected), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--coverage-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-patch-items", type=int, default=3000)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.db), Path(args.coverage_dir), Path(args.out), Path(args.report), args.max_patch_items, args.execute), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
