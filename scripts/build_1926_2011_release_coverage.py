#!/usr/bin/env python3
"""Build final 1926-2011 release coverage across release layers."""

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

from collection_expansion_common import now_iso, table_exists, write_csv
from lib.final_release import DECADES, PRIORITY_STATES, TIME_BANDS, band_for_year, frontend_map_points, source_is_concentrated, write_count_csv
from migrate_research_volume_expansion_v1 import migrate as migrate_volume


COVERAGE_FIELDS = ["band", "start_year", "end_year", "accepted_public_records", "public_map_records", "provisional_records", "metadata_only_gap_layer", "target_gap_leads", "auxiliary_source_intelligence", "visible_coverage_items", "total_items"]
GAP_FIELDS = ["gap_type", "band", "state", "observed_value", "threshold", "severity", "explanation", "requires_bounded_patch"]


def collect_items(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows: list[dict[str, Any]] = []
    if table_exists(conn, "records"):
        for row in conn.execute("SELECT record_id, title, year, url, publication FROM records WHERE year BETWEEN 1926 AND 2011"):
            rows.append({"layer": "accepted_public_records", "id": row["record_id"], "year": row["year"], "state": "unknown", "source_family": row["publication"] or "records", "route_family": "accepted_record", "title": row["title"], "url": row["url"]})
    if table_exists(conn, "record_locations") and table_exists(conn, "locations") and table_exists(conn, "records"):
        for row in conn.execute(
            """
            SELECT r.record_id, r.year, l.state_territory AS state
            FROM record_locations rl
            JOIN records r ON r.record_id=rl.record_id
            JOIN locations l ON l.location_id=rl.location_id
            WHERE r.year BETWEEN 1926 AND 2011
            """
        ):
            rows.append({"layer": "public_map_records", "id": row["record_id"], "year": row["year"], "state": row["state"] or "unknown", "source_family": "public_map", "route_family": "public_map"})
    if table_exists(conn, "provisional_records"):
        for row in conn.execute("SELECT provisional_record_id, inferred_year, source_publication_year, target_state, source_name, route_family FROM provisional_records WHERE COALESCE(inferred_year, source_publication_year, coverage_start_year) BETWEEN 1926 AND 2011"):
            year = row["inferred_year"] or row["source_publication_year"]
            rows.append({"layer": "provisional_records", "id": row["provisional_record_id"], "year": year, "state": row["target_state"] or "unknown", "source_family": row["source_name"] or "provisional", "route_family": row["route_family"] or ""})
    if table_exists(conn, "target_gap_leads"):
        for row in conn.execute("SELECT lead_id, lead_type, inferred_year, coverage_start_year, target_state, source_family, route_family, source_name, title, url FROM target_gap_leads WHERE COALESCE(inferred_year, coverage_start_year) BETWEEN 1926 AND 2011"):
            year = row["inferred_year"] or row["coverage_start_year"]
            layer = "metadata_only_gap_layer" if row["lead_type"] == "METADATA_ONLY_1955_1976_LEAD" else "target_gap_leads"
            rows.append({"layer": layer, "id": row["lead_id"], "year": year, "state": row["target_state"] or "unknown", "source_family": row["source_family"] or row["source_name"] or "", "route_family": row["route_family"] or "", "title": row["title"], "url": row["url"]})
    if table_exists(conn, "research_volume_items"):
        for row in conn.execute("SELECT item_id, layer, inferred_year, target_state, source_family, route_family, source_name FROM research_volume_items WHERE inferred_year BETWEEN 1926 AND 2011"):
            layer = "metadata_only_gap_layer" if row["layer"] == "metadata_only_lead" else ("target_gap_leads" if row["layer"] == "target_gap_lead" else "auxiliary_source_intelligence")
            rows.append({"layer": layer, "id": row["item_id"], "year": row["inferred_year"], "state": row["target_state"] or "unknown", "source_family": row["source_family"] or row["source_name"] or "", "route_family": row["route_family"] or ""})
    return rows


def build(db_path: Path, freeze_path: Path, out_dir: Path, execute: bool) -> dict[str, object]:
    migrate_volume(db_path)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8")) if freeze_path.exists() else {}
    with sqlite3.connect(db_path) as conn:
        items = collect_items(conn)
    by_band: dict[str, Counter] = {label: Counter() for label, _, _ in TIME_BANDS}
    by_decade: Counter = Counter()
    by_state: Counter = Counter()
    by_layer: Counter = Counter()
    concentration: dict[str, Counter] = defaultdict(Counter)
    for item in items:
        band = band_for_year(item.get("year"))
        if band in by_band:
            by_band[band][item["layer"]] += 1
            concentration[band][f"{item.get('source_family') or item.get('route_family') or 'unknown'}"] += 1
        decade = band_for_year(item.get("year"), DECADES)
        if decade not in {"unknown", "outside"}:
            by_decade[decade] += 1
        by_state[item.get("state") or "unknown"] += 1
        by_layer[item["layer"]] += 1
    coverage_rows = []
    gap_rows = []
    for label, start, end in TIME_BANDS:
        counts = by_band[label]
        visible = counts.get("accepted_public_records", 0) + counts.get("metadata_only_gap_layer", 0) + counts.get("target_gap_leads", 0)
        total = sum(counts.values())
        row = {
            "band": label,
            "start_year": start,
            "end_year": end,
            "accepted_public_records": counts.get("accepted_public_records", 0),
            "public_map_records": counts.get("public_map_records", 0),
            "provisional_records": counts.get("provisional_records", 0),
            "metadata_only_gap_layer": counts.get("metadata_only_gap_layer", 0),
            "target_gap_leads": counts.get("target_gap_leads", 0),
            "auxiliary_source_intelligence": counts.get("auxiliary_source_intelligence", 0),
            "visible_coverage_items": visible,
            "total_items": total,
        }
        coverage_rows.append(row)
        if visible == 0:
            gap_rows.append({"gap_type": "CRITICAL_HARD_GAP", "band": label, "state": "", "observed_value": 0, "threshold": 1, "severity": "FAIL", "explanation": "No accepted, metadata-only, or lead coverage exists.", "requires_bounded_patch": "yes"})
        elif visible < 25:
            gap_rows.append({"gap_type": "DISPLAY_HARD_GAP", "band": label, "state": "", "observed_value": visible, "threshold": 25, "severity": "WARN", "explanation": "Visible coverage is thin but not empty.", "requires_bounded_patch": "yes"})
        if row["accepted_public_records"] < 5 and visible >= 25:
            gap_rows.append({"gap_type": "RECORD_HARD_GAP", "band": label, "state": "", "observed_value": row["accepted_public_records"], "threshold": 5, "severity": "WARN", "explanation": "Accepted public records are sparse, but metadata/lead coverage exists.", "requires_bounded_patch": "no"})
        if row["public_map_records"] < 5 and visible >= 25:
            gap_rows.append({"gap_type": "MAP_HARD_GAP", "band": label, "state": "", "observed_value": row["public_map_records"], "threshold": 5, "severity": "WARN", "explanation": "Coverage exists but accepted public map evidence is sparse.", "requires_bounded_patch": "no"})
        top_count = concentration[label].most_common(1)[0][1] if concentration[label] else 0
        if total and top_count / total > 0.75:
            gap_rows.append({"gap_type": "SOURCE_HARD_GAP", "band": label, "state": "", "observed_value": round(top_count / total * 100, 2), "threshold": 75, "severity": "WARN", "explanation": "One source family dominates the band.", "requires_bounded_patch": "no"})
    for state in PRIORITY_STATES:
        count = by_state.get(state, 0)
        if count < 25:
            gap_rows.append({"gap_type": "STATE_HARD_GAP", "band": "1926-2011", "state": state, "observed_value": count, "threshold": 25, "severity": "WARN", "explanation": "Priority-state coverage is below floor.", "requires_bounded_patch": "yes"})
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "release_coverage_1926_2011.csv", coverage_rows, COVERAGE_FIELDS)
    write_csv(out_dir / "release_coverage_by_decade.csv", [{"decade": k, "count": v} for k, v in by_decade.most_common()], ["decade", "count"])
    write_count_csv(out_dir / "release_coverage_by_state.csv", by_state, "state")
    write_count_csv(out_dir / "release_coverage_by_layer.csv", by_layer, "layer")
    write_csv(out_dir / "hard_gap_report.csv", gap_rows, GAP_FIELDS)
    critical = [row for row in gap_rows if row["gap_type"] == "CRITICAL_HARD_GAP"]
    display = [row for row in gap_rows if row["gap_type"] == "DISPLAY_HARD_GAP"]
    lines = [
        "# 1926-2011 Release Coverage Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Freeze ID: `{freeze.get('freeze_id', 'unknown')}`",
        f"- Coverage items counted: `{len(items)}`",
        f"- Critical hard gaps: `{len(critical)}`",
        f"- Display hard gaps: `{len(display)}`",
        "- Public records mutated: `no`",
        "",
        "## Band Coverage",
    ]
    lines.extend([f"- `{row['band']}`: visible {row['visible_coverage_items']}, accepted {row['accepted_public_records']}, metadata {row['metadata_only_gap_layer']}, leads {row['target_gap_leads']}" for row in coverage_rows])
    lines.extend(["", "## Interpretation", "- True record gaps remain distinct from display/metadata/source-chain gaps.", "- Metadata-only and lead layers are not accepted public records."])
    (out_dir / "release_coverage_1926_2011_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    hard_lines = ["# 1926-2011 Hard Gap Report", "", f"- Generated: `{now_iso()}`", f"- Critical hard gaps: `{len(critical)}`", f"- Patch required: `{'yes' if any(row['requires_bounded_patch'] == 'yes' for row in gap_rows) else 'no'}`", "", "## Gaps"]
    hard_lines.extend([f"- `{row['gap_type']}` / `{row['band']}` {row['state']}: {row['observed_value']} (threshold {row['threshold']}) - {row['explanation']}" for row in gap_rows] or ["- No critical/display hard gaps."])
    (out_dir / "hard_gap_report.md").write_text("\n".join(hard_lines) + "\n", encoding="utf-8")
    return {"items": len(items), "critical_hard_gaps": len(critical), "display_hard_gaps": len(display), "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.db), Path(args.freeze), Path(args.out_dir), args.execute), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
