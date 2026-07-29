#!/usr/bin/env python3
"""Build the canonical frontend count contract for post-release pages."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.post_release_site import (  # noqa: E402
    EXPECTED_ACCEPTED_PUBLIC_MAP,
    LAYER_RULES,
    PROTECTED_LABELS,
    current_count_sources,
    read_json,
    write_json,
    write_markdown,
)


def build_contract(
    db_path: Path,
    frontend_data: Path,
    release_package: Path,
    coverage_dir: Path,
    map_dir: Path,
    redirect_dir: Path,
    out: Path,
    report: Path,
    execute: bool,
) -> dict[str, object]:
    sources = current_count_sources(db_path, frontend_data, release_package, coverage_dir, map_dir, redirect_dir)
    counts = sources["canonical"]
    failures: list[str] = []
    warnings: list[str] = []

    if counts["accepted_public_map_points"] != EXPECTED_ACCEPTED_PUBLIC_MAP:
        failures.append(f"accepted_public_map_points expected {EXPECTED_ACCEPTED_PUBLIC_MAP}, got {counts['accepted_public_map_points']}")
    if counts["metadata_gap_items"] + counts["lead_overlay_items"] + sources["frontend"]["accepted_public_records"] == counts["accepted_public_records"]:
        failures.append("metadata/lead counts appear mixed into accepted public record count")
    if sources["release_package"].get("metadata_overlay") is not None and int(sources["release_package"].get("metadata_overlay") or 0) != counts["metadata_gap_items"]:
        failures.append("release package metadata_overlay disagrees with canonical metadata_gap_items")
    if sources["release_package"].get("lead_overlay") is not None and int(sources["release_package"].get("lead_overlay") or 0) != counts["lead_overlay_items"]:
        failures.append("release package lead_overlay disagrees with canonical lead_overlay_items")
    if counts["critical_hard_gaps_1926_2011"] or counts["display_hard_gaps_1926_2011"]:
        failures.append("coverage hard gaps are nonzero")
    if sources["db"].get("records_table") and sources["db"]["records_table"] != counts["accepted_public_records"]:
        warnings.append(
            f"DB records table inventory {sources['db']['records_table']} differs from frontend accepted display count {counts['accepted_public_records']}; frontend contract uses displayed accepted records"
        )

    contract = {
        "generated_at": now_iso(),
        "release_id": "post_release_site_integration_001",
        "counts": counts,
        "labels": PROTECTED_LABELS,
        "rules": LAYER_RULES,
        "comparisons": sources,
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "warnings": warnings,
    }

    if execute:
        write_json(out, contract)

    report_lines = [
        "# Frontend Count Contract Report",
        "",
        f"- Generated: `{contract['generated_at']}`",
        f"- Status: `{contract['status']}`",
        f"- Output: `{out}`",
        "",
        "## Canonical Counts",
    ]
    for key, label in PROTECTED_LABELS.items():
        report_lines.append(f"- {label}: `{counts.get(key, 0)}`")
    report_lines.extend([
        f"- Critical hard gaps 1926-2011: `{counts['critical_hard_gaps_1926_2011']}`",
        f"- Display hard gaps 1926-2011: `{counts['display_hard_gaps_1926_2011']}`",
        f"- ID redirects: `{counts['id_redirects']}`",
        f"- URL redirects: `{counts['url_redirects']}`",
        "",
        "## Comparisons",
        f"- DB accepted inventory: `{sources['db'].get('records_table', 0)}`",
        f"- Frontend accepted records: `{sources['frontend'].get('accepted_public_records', 0)}`",
        f"- Frontend accepted map points: `{sources['frontend'].get('accepted_public_map_points', 0)}`",
        f"- Release package accepted records: `{sources['release_package'].get('accepted_public_records', 0)}`",
        f"- Map layer accepted public map: `{sources['map'].get('accepted_public_map', 0)}`",
        "",
        "## Layer Rules",
        "- Metadata-only gap items are not accepted public records.",
        "- Research leads are not accepted public records.",
        "- Map overlay items are not accepted public map points.",
    ])
    if warnings:
        report_lines.extend(["", "## Warnings", *[f"- {item}" for item in warnings]])
    if failures:
        report_lines.extend(["", "## Failures", *[f"- {item}" for item in failures]])
    write_markdown(report, report_lines)

    if failures:
        raise SystemExit(json.dumps({"status": "FAIL", "failures": failures}, indent=2))
    return contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--frontend-data", required=True)
    parser.add_argument("--release-package", required=True)
    parser.add_argument("--coverage-dir", required=True)
    parser.add_argument("--map-dir", required=True)
    parser.add_argument("--redirect-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = build_contract(
        Path(args.db),
        Path(args.frontend_data),
        Path(args.release_package),
        Path(args.coverage_dir),
        Path(args.map_dir),
        Path(args.redirect_dir),
        Path(args.out),
        Path(args.report),
        args.execute,
    )
    print(json.dumps({"status": result["status"], "out": args.out}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
