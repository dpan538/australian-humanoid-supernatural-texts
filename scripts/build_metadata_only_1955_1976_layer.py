#!/usr/bin/env python3
"""Build a metadata-only 1955-1976 observational lead layer."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.lead_intelligence import counter_rows, extract_date_signal, group_counter, metadata_class, top_groups, write_count_csv
from lib.target_gap_leads import LEAD_FIELDS, read_leads
from migrate_target_gap_leads_v1 import migrate


LAYER_FIELDS = LEAD_FIELDS + ["metadata_only_classification", "year_band"]
CLUSTER_FIELDS = ["route_family", "target_state", "metadata_only_classification", "lead_count", "priority_leads", "max_lead_score"]


def year_band(row: dict[str, object]) -> str:
    try:
        year = int(row.get("inferred_year") or row.get("coverage_start_year") or 0)
    except (TypeError, ValueError):
        return "unknown"
    if 1955 <= year <= 1959:
        return "1955-1959"
    if 1960 <= year <= 1969:
        return "1960-1969"
    if 1970 <= year <= 1976:
        return "1970-1976"
    return "other"


def build_layer(db_path: Path, out_dir: Path, execute: bool) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
    layer = []
    for row in leads:
        working = dict(row)
        if not (working.get("temporal_signal") or working.get("inferred_year")):
            date = extract_date_signal(working)
            if date["date_status"].startswith("salvaged"):
                working["temporal_signal"] = date["temporal_signal"]
                working["inferred_year"] = date["inferred_year"]
                working["coverage_start_year"] = date["coverage_start_year"]
                working["coverage_end_year"] = date["coverage_end_year"]
        classification = metadata_class(working)
        if not classification:
            continue
        working["metadata_only_classification"] = classification
        working["year_band"] = year_band(working)
        layer.append(working)
    layer.sort(key=lambda row: (-float(row.get("lead_score") or 0), str(row.get("lead_id") or "")))
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "metadata_only_1955_1976_leads.csv", layer, LAYER_FIELDS)
    write_count_csv(out_dir / "metadata_only_by_state.csv", counter_rows(group_counter(layer, "target_state")))
    write_count_csv(out_dir / "metadata_only_by_route_family.csv", counter_rows(group_counter(layer, "route_family")))
    write_count_csv(out_dir / "metadata_only_by_source_family.csv", counter_rows(group_counter(layer, "source_family")))
    write_count_csv(out_dir / "metadata_only_by_year_band.csv", counter_rows(group_counter(layer, "year_band")))
    clusters = top_groups(layer, "route_family", "target_state", "metadata_only_classification", limit=50)
    write_csv(out_dir / "metadata_only_priority_clusters.csv", clusters, CLUSTER_FIELDS)
    classification_counts = Counter(row["metadata_only_classification"] for row in layer)
    lines = [
        "# Metadata-Only 1955-1976 Lead Layer",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Metadata-only leads: `{len(layer)}`",
        "- Public records created: `0`",
        "- Map flags published: `0`",
        "- Frontend records promoted: `0`",
        "",
        "## Classifications",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in classification_counts.most_common()] or ["- None"])
    lines.extend(["", "## Top Priority Clusters"])
    lines.extend([f"- `{row['route_family']}` / `{row['target_state']}` / `{row['metadata_only_classification']}`: {row['lead_count']} leads" for row in clusters[:12]] or ["- None"])
    (out_dir / "metadata_only_1955_1976_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"metadata_only_leads": len(layer), "classifications": dict(classification_counts), "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build_layer(Path(args.db), Path(args.out_dir), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
