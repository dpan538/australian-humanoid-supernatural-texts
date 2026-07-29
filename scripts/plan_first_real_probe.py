#!/usr/bin/env python3
"""Plan a safe first real Trove metadata-only probe."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_registry, now_iso, write_csv


PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
TIME_PRIORITY = {"1926_1939": 0, "1940_1954": 1, "1955_1964": 2, "1965_1976": 3}


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def preferred_source_ids(row: dict[str, Any]) -> set[str]:
    raw = row.get("preferred_source_ids_json") or "[]"
    try:
        value = json.loads(raw)
        return {str(item) for item in value} if isinstance(value, list) else set()
    except Exception:
        return set()


def is_trove_metadata_row(row: dict[str, Any], registry: dict[str, dict[str, Any]]) -> bool:
    route_family = str(row.get("route_family") or "").lower()
    source_ids = preferred_source_ids(row)
    routes = [registry.get(source_id, {}) for source_id in source_ids]
    if "trove" not in route_family and not any("trove" in str(route.get("source_id") or "").lower() for route in routes):
        return False
    if str(row.get("route_source_tier") or "").upper() != "A":
        return False
    if str(row.get("should_fetch") or "").lower() not in {"true", "1", "yes"}:
        return False
    if str(row.get("should_manual_review") or "").lower() in {"true", "1", "yes"}:
        return False
    if str(row.get("route_safety_class") or "").lower() not in {"automated_metadata_api", "metadata_first"}:
        return False
    modes = {str(route.get("evidence_or_discovery") or "") for route in routes if route}
    if modes and not modes.intersection({"evidence_possible", "evidence_only_if_original_source_identified"}):
        return False
    return True


def score_row(row: dict[str, Any]) -> tuple[int, str]:
    score = 0
    reasons = []
    state = str(row.get("target_state") or "")
    time_band = str(row.get("time_band") or "")
    if state in PRIORITY_STATES:
        score += 50
        reasons.append("priority_state")
    if time_band in {"1926_1939", "1940_1954"}:
        score += 35
        reasons.append("strong_trove_period")
    elif time_band in {"1955_1964", "1965_1976"}:
        score += 15
        reasons.append("later_metadata_exploration")
    if str(row.get("target_locality") or "").strip():
        score += 10
        reasons.append("locality_query")
    return score, ";".join(reasons)


def plan_probe(query_plan: Path, registry_path: Path, out_path: Path, report_path: Path, max_queries: int) -> list[dict[str, Any]]:
    registry_rows = load_registry(registry_path)
    registry = {str(row["source_id"]): row for row in registry_rows}
    eligible: list[dict[str, Any]] = []
    for row in read_rows(query_plan):
        if not is_trove_metadata_row(row, registry):
            continue
        scored = dict(row)
        score, reasons = score_row(row)
        scored["first_probe_score"] = score
        scored["first_probe_reason"] = reasons
        scored["probe_warning"] = "metadata_only_stage_candidates_no_acceptance_no_map_publication"
        eligible.append(scored)
    eligible.sort(key=lambda row: (-int(row["first_probe_score"]), TIME_PRIORITY.get(str(row.get("time_band")), 99), str(row.get("target_state")), str(row.get("query_id"))))

    selected: list[dict[str, Any]] = []
    covered_bands: set[str] = set()
    for band in ["1926_1939", "1940_1954", "1955_1964", "1965_1976"]:
        for row in eligible:
            if row.get("time_band") == band and row not in selected:
                selected.append(row)
                covered_bands.add(band)
                break
    for row in eligible:
        if len(selected) >= max_queries:
            break
        if row not in selected:
            selected.append(row)

    fieldnames = list(selected[0].keys()) if selected else list(read_rows(query_plan)[0].keys()) + ["first_probe_score", "first_probe_reason", "probe_warning"]
    write_csv(out_path, selected[:max_queries], fieldnames)
    command = (
        "TROVE_API_KEY=... python3 scripts/probe_trove_metadata_batch.py \\\n"
        "  --db data/processed/australian_humanoid_figures.sqlite \\\n"
        f"  --query-plan {out_path} \\\n"
        "  --run-id trove_first_real_probe_001 \\\n"
        "  --limit 50 \\\n"
        "  --max-results-per-query 5 \\\n"
        "  --execute"
    )
    lines = [
        "# First Real Trove Metadata Probe Plan",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Planned queries: `{len(selected[:max_queries])}`",
        f"- Covered time bands: `{', '.join(sorted(covered_bands))}`",
        "- This stages metadata-only candidates.",
        "- This does not accept records.",
        "- This does not publish map flags.",
        "- Candidate scoring becomes meaningful only after this real probe stages candidates.",
        "",
        "## Command",
        "",
        "```bash",
        command,
        "```",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return selected[:max_queries]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-plan", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-queries", type=int, default=50)
    args = parser.parse_args()
    rows = plan_probe(Path(args.query_plan), Path(args.registry), Path(args.out), Path(args.report), args.max_queries)
    print(f"Wrote first real Trove probe plan with {len(rows)} queries: {args.out}")


if __name__ == "__main__":
    main()
