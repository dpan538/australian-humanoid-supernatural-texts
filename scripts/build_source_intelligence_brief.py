#!/usr/bin/env python3
"""Summarize what target-gap leads reveal about the source universe."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.lead_intelligence import METADATA_ROUTE_FAMILIES
from lib.target_gap_leads import read_leads
from migrate_target_gap_leads_v1 import migrate


def _top(counter: Counter, limit: int = 6) -> list[str]:
    return [f"- `{key or 'unknown'}`: {value}" for key, value in counter.most_common(limit)] or ["- None"]


def brief(db_path: Path, out: Path) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
    source_family_counts = Counter(row.get("source_family") or "unknown" for row in leads)
    route_counts = Counter(row.get("route_family") or "unknown" for row in leads)
    states = Counter(row.get("target_state") or "unknown" for row in leads)
    terms = Counter(row.get("term_signal") or "missing" for row in leads)
    blockers = Counter(row.get("constraint_blocker") or "unknown" for row in leads)
    rich_undated: Counter[str] = Counter()
    target_potential: Counter[str] = Counter()
    useful_routes: Counter[str] = Counter()
    for row in leads:
        family = row.get("source_family") or row.get("route_family") or "unknown"
        route = row.get("route_family") or "unknown"
        if row.get("constraint_blocker") == "missing_date":
            rich_undated[family] += 1
        if row.get("temporal_signal") or row.get("inferred_year") or row.get("priority_bucket") in {"PRIORITY_LEAD", "GOOD_LEAD"}:
            target_potential[family] += 1
        if route in METADATA_ROUTE_FAMILIES or any(token in str(route) for token in ["catalogue", "archive", "library", "museum", "council", "serial", "broadcast"]):
            useful_routes[route] += 1
    technical = sum(blockers.get(key, 0) for key in ["robots_unknown", "robots_denied", "missing_item_url", "field_mapping_sparse"])
    structural = sum(blockers.get(key, 0) for key in ["missing_date", "missing_term", "d_class_needs_original", "discovery_only_needs_evidence", "source_unknown", "ethics_sensitive"])
    undercovered = [state for state, count in states.items() if state != "unknown" and count < 100]
    most_material_constraint = "metadata-only/date-salvage policy" if blockers.get("missing_date", 0) > blockers.get("robots_unknown", 0) else "robots/permission clarification"
    lines = [
        "# Source Intelligence Brief",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Leads summarized: `{len(leads)}`",
        "",
        "## Rich But Undated Source Families",
    ]
    lines.extend(_top(rich_undated))
    lines.extend(["", "## Target-Period Potential"])
    lines.extend(_top(target_potential))
    lines.extend(["", "## State Coverage"])
    lines.extend(_top(states, 8))
    lines.append(f"- Undercovered states by current lead count threshold: `{', '.join(undercovered) if undercovered else 'none obvious from lead layer'}`")
    lines.extend(["", "## Term Signals"])
    lines.extend(_top(terms, 8))
    lines.append(f"- Leads missing a term signal: `{terms.get('missing', 0)}`")
    lines.extend(["", "## Best Source Families For Future Route Research"])
    lines.extend(_top(useful_routes, 8))
    lines.extend(
        [
            "",
            "## Technical vs Structural Blockers",
            f"- Technical blockers: `{technical}`",
            f"- Structural blockers: `{structural}`",
            "- Technical blockers are mostly robots/detail-fetch uncertainty.",
            "- Structural blockers are mostly missing date or missing term evidence in otherwise useful metadata.",
            "",
            "## Constraint Relaxation With Most Effect",
            f"- Most material relaxation: `{most_material_constraint}`",
            "- Trove API and tiny review remain optional, not default.",
            "- More equivalent crawling is not recommended until dedupe, date salvage, and metadata-only interpretation are exhausted.",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"leads": len(leads), "top_route": route_counts.most_common(1)[0][0] if route_counts else "", "top_blocker": blockers.most_common(1)[0][0] if blockers else "", "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(brief(Path(args.db), Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
