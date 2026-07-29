#!/usr/bin/env python3
"""Analyze target-gap lead blockers by route, source, state, and constraint."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.target_gap_leads import domain_for, read_leads
from migrate_target_gap_leads_v1 import migrate


FIELDS = ["constraint_blocker", "dimension", "value", "lead_count", "recommendation"]


def recommendation(blocker: str, value: str) -> str:
    if blocker in {"robots_unknown", "robots_denied"}:
        return "permission/robots clarification"
    if blocker == "missing_date":
        if value in {"museum_heritage_page", "council_local_studies", "state_library_catalogue", "local_history_serial", "state_archive_catalogue"}:
            return "date salvage only"
        return "metadata-only layer"
    if blocker == "missing_term":
        return "metadata-only layer"
    if blocker in {"d_class_needs_original", "discovery_only_needs_evidence", "source_unknown"}:
        return "source-chain remediation"
    if blocker == "ethics_sensitive":
        return "pause from future autonomous collection"
    return "keep as auxiliary lead"


def _dimension_rows(leads: list[dict[str, Any]], dimension: str, value_getter) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in leads:
        blocker = str(row.get("constraint_blocker") or "unknown")
        value = str(value_getter(row) or "unknown")
        counts[(blocker, value)] += 1
    rows = [
        {
            "constraint_blocker": blocker,
            "dimension": dimension,
            "value": value,
            "lead_count": count,
            "recommendation": recommendation(blocker, value),
        }
        for (blocker, value), count in counts.items()
    ]
    rows.sort(key=lambda row: (-row["lead_count"], row["constraint_blocker"], row["value"]))
    return rows


def analyze(db_path: Path, out: Path) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
    all_rows = []
    dimensions = {
        "route_family": lambda row: row.get("route_family"),
        "source_family": lambda row: row.get("source_family"),
        "state": lambda row: row.get("target_state"),
        "priority_bucket": lambda row: row.get("priority_bucket"),
        "lead_type": lambda row: row.get("lead_type"),
        "evidence_gap": lambda row: row.get("evidence_gap"),
        "robots_domain": lambda row: domain_for(row.get("url") or "") if "robots" in str(row.get("constraint_blocker") or "") else "",
        "d_class_access_platform": lambda row: row.get("source_name") or row.get("source_family") if "d_class" in str(row.get("evidence_gap") or "") or row.get("source_tier") == "D" else "",
    }
    for dimension, getter in dimensions.items():
        all_rows.extend(_dimension_rows(leads, dimension, getter))
    blocker_counts = Counter(row.get("constraint_blocker") or "unknown" for row in leads)
    top_missing_date_routes = [row for row in all_rows if row["constraint_blocker"] == "missing_date" and row["dimension"] == "route_family"][:10]
    out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out.with_suffix(".csv"), all_rows, FIELDS)
    lines = [
        "# Lead Blocker Analysis",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Leads analyzed: `{len(leads)}`",
        "",
        "## Blocker Counts",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in blocker_counts.most_common()] or ["- None"])
    lines.extend(["", "## Missing-Date Route Families"])
    lines.extend([f"- `{row['value']}`: {row['lead_count']} leads, recommendation `{row['recommendation']}`" for row in top_missing_date_routes] or ["- None"])
    lines.extend(["", "## Top Blocker Clusters"])
    lines.extend([f"- `{row['constraint_blocker']}` / `{row['dimension']}` / `{row['value']}`: {row['lead_count']} leads, recommendation `{row['recommendation']}`" for row in all_rows[:20]] or ["- None"])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"leads": len(leads), "top_blocker": blocker_counts.most_common(1)[0][0] if blocker_counts else "", "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(Path(args.db), Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
