#!/usr/bin/env python3
"""Build the owner-facing target-gap lead observation dashboard."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.target_gap_leads import read_leads
from migrate_target_gap_leads_v1 import migrate


LEAD_DIR = ROOT / "data" / "processed" / "v2" / "autoharvest" / "target_gap_leads"
METADATA_DIR = ROOT / "data" / "processed" / "v2" / "autoharvest" / "metadata_only_1955_1976"


def _csv_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in csv.DictReader(handle)))


def _top_csv(path: Path, label: str = "category", count: str = "count", limit: int = 5) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: -int(float(row.get(count) or 0)))
    return [f"- `{row.get(label) or 'unknown'}`: {row.get(count) or 0}" for row in rows[:limit]]


def dashboard(db_path: Path, out: Path) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
    total = len(leads)
    canonical = sum(1 for row in leads if row.get("duplicate_status") in {"canonical", "unique"})
    priority = sum(1 for row in leads if row.get("priority_bucket") == "PRIORITY_LEAD" and row.get("duplicate_status") in {"", "unchecked", "canonical", "unique"})
    bucket_counts = Counter(row.get("priority_bucket") or "unknown" for row in leads)
    blocker_counts = Counter(row.get("constraint_blocker") or "unknown" for row in leads)
    route_counts = Counter(row.get("route_family") or "unknown" for row in leads)
    date_salvaged = _csv_count(LEAD_DIR / "date_salvaged_leads.csv")
    still_missing = sum(1 for row in leads if "missing_date" in str(row.get("evidence_gap") or ""))
    metadata_count = _csv_count(METADATA_DIR / "metadata_only_1955_1976_leads.csv")
    date_done = (LEAD_DIR / "date_salvage_report.md").exists()
    metadata_done = (METADATA_DIR / "metadata_only_1955_1976_summary.md").exists()
    if not date_done:
        next_command = "make lead-date-salvage"
    elif not metadata_done:
        next_command = "make metadata-only-1955-1976-layer"
    else:
        next_command = "no new crawl; review dashboard only"
    lines = [
        "# Lead Observation Dashboard",
        "",
        f"- Generated: `{now_iso()}`",
        "",
        "## 1. Executive Decision",
        "- Strict records mode should remain closed.",
        "- Lead mode has enough data; do not run more lead crawling yet.",
        "- Analyze existing leads first through dedupe, date salvage, and metadata-only layering.",
        "",
        "## 2. Lead Inventory",
        f"- Total leads: `{total}`",
        f"- Unique/canonical leads after dedupe: `{canonical or 'dedupe not run'}`",
        f"- Priority leads: `{priority}`",
        f"- Weak leads: `{bucket_counts.get('WEAK_LEAD', 0)}`",
        f"- Hold leads: `{bucket_counts.get('HOLD', 0)}`",
        f"- Sensitive holds: `{bucket_counts.get('SENSITIVE_HOLD', 0)}`",
        f"- Blocked robots leads: `{bucket_counts.get('BLOCKED_ROBOTS', 0)}`",
        "",
        "## 3. Date Problem",
        f"- Missing-date blocker count: `{blocker_counts.get('missing_date', 0)}`",
        f"- Dates salvaged: `{date_salvaged}`",
        f"- Still missing date after salvage: `{still_missing}`",
        "- Strongest date-bearing clusters:",
    ]
    lines.extend(_top_csv(LEAD_DIR / "lead_clusters.csv", "cluster_label", "lead_count", 5) or ["- Not available"])
    lines.extend(
        [
            "",
            "## 4. Metadata-Only 1955-1976 Layer",
            f"- Metadata-only 1955-1976 leads: `{metadata_count}`",
            "- By state:",
        ]
    )
    lines.extend(_top_csv(METADATA_DIR / "metadata_only_by_state.csv") or ["- Not available"])
    lines.append("- By route family:")
    lines.extend(_top_csv(METADATA_DIR / "metadata_only_by_route_family.csv") or ["- Not available"])
    lines.append("- By source family:")
    lines.extend(_top_csv(METADATA_DIR / "metadata_only_by_source_family.csv") or ["- Not available"])
    lines.extend(["", "## 5. Source Intelligence", "- Top source clusters:"])
    lines.extend([f"- `{key}`: {value} leads" for key, value in route_counts.most_common(8)] or ["- None"])
    lines.append("- Route families producing useful leads: museum, council local studies, state-library catalogues, local-history serials, state archives, and broadcast catalogues.")
    lines.append("- Route families producing mostly auxiliary/no-date leads should stay in analysis mode until date salvage improves them.")
    lines.extend(
        [
            "",
            "## 6. Constraint Decision",
            "- Strict no-credential records mode: `closed`",
            "- Lead mode: `populated`",
            "- More lead crawling: `not now`",
            "- Tiny review: `optional only`",
            "- Trove API: `optional, not default`",
            "- D-class access layer: `optional`",
            "",
            "## 7. Next Exact Command",
            f"- `{next_command}`",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"total_leads": total, "canonical_leads": canonical, "priority_leads": priority, "metadata_only_leads": metadata_count, "next_command": next_command, "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(dashboard(Path(args.db), Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
