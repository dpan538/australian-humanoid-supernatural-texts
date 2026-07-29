#!/usr/bin/env python3
"""Build release chart data with explicit layer separation."""

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

from collection_expansion_common import now_iso
from lib.post_release_site import (  # noqa: E402
    counter_rows,
    read_csv_rows,
    read_json,
    table_exists,
    table_rows,
    write_json,
    write_markdown,
)


def chart(title: str, description: str, data: list[dict[str, Any]], caveat: str, provenance: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "description": description,
        "layer_definitions": {
            "accepted_public_records": "Accepted public records",
            "metadata_only_gap_layer": "Metadata-only gap items; not public records",
            "target_gap_leads": "Research leads; not public records",
            "auxiliary_source_intelligence": "Source intelligence; not public records",
            "accepted_public_map": "Accepted public map points",
            "metadata_place_overlay": "Map overlay items; not accepted map points",
            "lead_place_overlay": "Lead map overlays; not accepted map points",
        },
        "data": data,
        "caveat": caveat,
        "source_file_provenance": provenance,
        "generated_at": now_iso(),
    }


def release_layer_rows(db_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not db_path.exists():
        return rows
    with sqlite3.connect(db_path) as conn:
        if table_exists(conn, "release_metadata_gap_items"):
            rows.extend(dict(row, layer="metadata_only_gap_layer") for row in table_rows(conn, "release_metadata_gap_items"))
        if table_exists(conn, "release_lead_overlay_items"):
            rows.extend(dict(row, layer="target_gap_leads") for row in table_rows(conn, "release_lead_overlay_items"))
        if table_exists(conn, "release_source_intelligence_items"):
            rows.extend(dict(row, layer="auxiliary_source_intelligence") for row in table_rows(conn, "release_source_intelligence_items"))
    return rows


def build_charts(
    db_path: Path,
    count_contract: Path,
    coverage_dir: Path,
    map_dir: Path,
    release_package: Path,
    out: Path,
    report: Path,
    execute: bool,
) -> dict[str, object]:
    contract = read_json(count_contract, {}) or {}
    counts = contract.get("counts", {})
    coverage = read_csv_rows(coverage_dir / "release_coverage_1926_2011.csv")
    decades = read_csv_rows(coverage_dir / "release_coverage_by_decade.csv")
    states = read_csv_rows(coverage_dir / "release_coverage_by_state.csv")
    layer_rows = read_csv_rows(coverage_dir / "release_coverage_by_layer.csv")
    map_counts = read_json(map_dir / "map_layer_counts.json", {}) or {}
    release_counts = read_json(release_package / "release-counts.json", {}) or {}
    rows = release_layer_rows(db_path)

    source_family_counts: Counter[str] = Counter()
    source_tier_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    metadata_1955_1976: Counter[str] = Counter()
    limitations = Counter({
        "accepted_record_gaps_documented": 1,
        "metadata_only_not_proof": 1,
        "research_leads_require_review": 1,
        "map_overlay_not_habitat": 1,
    })
    for row in rows:
        source_family_counts[str(row.get("source_family") or row.get("route_family") or "unknown")] += 1
        source_tier_counts[str(row.get("source_tier") or "unknown")] += 1
        blocker_counts[str(row.get("blocker") or row.get("evidence_gap") or "not_record_gate_complete")] += 1
        start = int(row.get("coverage_start_year") or row.get("inferred_year") or 0)
        end = int(row.get("coverage_end_year") or row.get("inferred_year") or 0)
        if row.get("layer") == "metadata_only_gap_layer" and start <= 1976 and end >= 1955:
            metadata_1955_1976[str(row.get("target_state") or "unknown")] += 1

    charts = [
        chart(
            "1926-2011 coverage by time band and layer",
            "Multi-layer coverage split into accepted records, metadata-only items, leads, and auxiliary intelligence.",
            coverage,
            "Coverage items are not accepted-public-record totals.",
            [str(coverage_dir / "release_coverage_1926_2011.csv")],
        ),
        chart("Decade coverage by layer", "Decade coverage rows for release display.", decades, "Decade rows are coverage counts.", [str(coverage_dir / "release_coverage_by_decade.csv")]),
        chart("Coverage by state and layer", "State and territory coverage, including release layers.", states, "State coverage may include research-layer rows.", [str(coverage_dir / "release_coverage_by_state.csv")]),
        chart(
            "Accepted map vs overlay map layers",
            "Accepted map points are separate from metadata and lead overlays.",
            [
                {"layer": "accepted_public_map", "count": map_counts.get("accepted_public_map", 0)},
                {"layer": "metadata_place_overlay", "count": map_counts.get("metadata_place_overlay", 0)},
                {"layer": "lead_place_overlay", "count": map_counts.get("lead_place_overlay", 0)},
            ],
            "Overlay rows are not accepted public map points.",
            [str(map_dir / "map_layer_counts.json")],
        ),
        chart("Source family distribution by layer", "Release-layer source family distribution.", counter_rows(source_family_counts, "source_family"), "Research-layer source families remain labelled.", ["release layer DB tables"]),
        chart("Source tier distribution by layer", "Release-layer source tier distribution.", counter_rows(source_tier_counts, "source_tier"), "Tiers do not promote leads into accepted records.", ["release layer DB tables"]),
        chart("Blocker distribution for leads", "Evidence gaps and blockers on release-layer rows.", counter_rows(blocker_counts, "blocker"), "Blockers remain visible instead of being hidden.", ["release layer DB tables"]),
        chart("Redirect counts", "ID and URL redirect counts used by the frontend.", [{"type": "id_redirects", "count": counts.get("id_redirects", 0)}, {"type": "url_redirects", "count": counts.get("url_redirects", 0)}], "Redirects are route resolution data, not evidence replacement.", [str(count_contract)]),
        chart("Metadata-only 1955-1976 distribution", "Metadata-only release rows overlapping the target gap by state.", counter_rows(metadata_1955_1976, "state"), "Metadata-only rows are not accepted records.", ["release_metadata_gap_items"]),
        chart("Known limitations", "Documented limitations retained in the release.", counter_rows(limitations, "limitation"), "Limitations are part of the release interpretation.", ["final release audit"]),
    ]

    failures = []
    map_total = sum(int(row["count"]) for row in charts[3]["data"])
    expected_map_total = int(counts.get("accepted_public_map_points", 0)) + int(counts.get("metadata_gap_items", 0)) + int(counts.get("lead_overlay_items", 0))
    if map_total != expected_map_total:
        failures.append(f"map chart total {map_total} conflicts with count contract {expected_map_total}")
    if int(release_counts.get("metadata_overlay", 0)) != int(counts.get("metadata_gap_items", 0)):
        failures.append("metadata overlay chart input conflicts with count contract")
    if int(release_counts.get("lead_overlay", 0)) != int(counts.get("lead_overlay_items", 0)):
        failures.append("lead overlay chart input conflicts with count contract")

    payload = {
        "generated_at": now_iso(),
        "schema": "release-charts/v1",
        "contract_counts": counts,
        "charts": charts,
    }
    if execute:
        write_json(out, payload)
    write_markdown(
        report,
        [
            "# Release Charts Report",
            "",
            f"- Generated: `{payload['generated_at']}`",
            f"- Status: `{'FAIL' if failures else 'PASS'}`",
            f"- Charts generated: `{len(charts)}`",
            f"- Accepted public map count: `{counts.get('accepted_public_map_points', 0)}`",
            f"- Metadata-only overlay count: `{counts.get('metadata_gap_items', 0)}`",
            f"- Lead overlay count: `{counts.get('lead_overlay_items', 0)}`",
            "",
            "## Rules",
            "- Charts keep accepted records, metadata-only items, research leads, and source intelligence as separate layers.",
            "- Any mixed chart carries a caveat and provenance.",
            *(["", "## Failures", *[f"- {failure}" for failure in failures]] if failures else []),
        ],
    )
    if failures:
        raise SystemExit(json.dumps({"status": "FAIL", "failures": failures}, indent=2))
    return {"status": "PASS", "charts": len(charts)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--count-contract", required=True)
    parser.add_argument("--coverage-dir", required=True)
    parser.add_argument("--map-dir", required=True)
    parser.add_argument("--release-package", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = build_charts(
        Path(args.db),
        Path(args.count_contract),
        Path(args.coverage_dir),
        Path(args.map_dir),
        Path(args.release_package),
        Path(args.out),
        Path(args.report),
        args.execute,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
