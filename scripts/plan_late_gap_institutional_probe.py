#!/usr/bin/env python3
"""Plan 1955-1976 institutional/local/broadcast metadata probes."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_registry, load_yaml, make_query, now_iso, write_csv


TARGET_BANDS = {"1955_1964", "1965_1976"}
PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
PREFERRED_FAMILIES = {
    "state_library_catalogue",
    "state_archive_catalogue",
    "local_history_serial",
    "council_local_studies",
    "broadcast_catalogue",
    "museum_heritage_page",
    "heritage_register",
}
AUTO_TIERS = {"A", "B", "C"}
FIELDS = [
    "query_id",
    "time_band",
    "target_state",
    "target_locality",
    "term_family",
    "term",
    "route_id",
    "source_id",
    "source_name",
    "route_family",
    "source_tier",
    "access_method",
    "collection_mode",
    "query_string",
    "should_fetch",
    "should_manual_review",
    "ethics_risk",
    "sample_weight",
    "sample_reason",
]


def safe_route_for_auto(route: dict[str, Any]) -> bool:
    return (
        str(route.get("route_family")) in PREFERRED_FAMILIES
        and str(route.get("source_tier")) in AUTO_TIERS
        and str(route.get("evidence_or_discovery")) != "discovery_only"
        and str(route.get("evidence_or_discovery")) != "manual_only_sensitive"
        and str(route.get("access_method")) in {"api", "public_html", "catalogue_manual_or_html"}
        and "tourism" not in str(route.get("source_name") or "").lower()
        and "wikipedia" not in str(route.get("source_name") or "").lower()
        and "paranormal" not in str(route.get("source_name") or "").lower()
    )


def state_route(route: dict[str, Any], state: str) -> bool:
    states = route.get("states") or []
    return state in states


def build_rows(matrix_path: Path, registry_path: Path, max_automated: int, max_manual: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matrix = load_yaml(matrix_path)
    registry = load_registry(registry_path)
    states = matrix.get("states", {})
    bands = {item["id"]: item for item in matrix.get("time_bands", []) if item.get("id") in TARGET_BANDS}
    terms_by_family = matrix.get("term_families", {})
    auto_rows: list[dict[str, Any]] = []
    manual_rows: list[dict[str, Any]] = []
    for band_id, band in bands.items():
        for state, state_cfg in states.items():
            if state not in PRIORITY_STATES:
                continue
            localities = state_cfg.get("locality_terms") or [""]
            for family, family_cfg in terms_by_family.items():
                ethics = str(family_cfg.get("ethics_risk") or "")
                sensitive = ethics in {"medium_high", "high"} or family == "named_local_legend"
                if family == "context_filter_exclusions":
                    continue
                for term in (family_cfg.get("terms") or [])[:4]:
                    for locality in localities[:6]:
                        query = make_query(str(term), str(locality), state, int(band["start_year"]), int(band["end_year"]), trove=False)
                        for route in registry:
                            if not state_route(route, state):
                                continue
                            route_family = str(route.get("route_family") or "")
                            if route.get("evidence_or_discovery") == "manual_only_sensitive":
                                target = manual_rows
                                mode = "manual_review_only"
                                should_fetch = "false"
                                should_manual = "true"
                                reason = "manual_sensitive_route"
                            elif safe_route_for_auto(route) and not sensitive:
                                target = auto_rows
                                mode = "automated_metadata_or_official_search_page"
                                should_fetch = "true"
                                should_manual = "false"
                                reason = "late_gap_priority_state;official_metadata_route"
                            else:
                                continue
                            if route_family not in PREFERRED_FAMILIES and target is auto_rows:
                                continue
                            row = {
                                "query_id": f"late_{band_id}_{state}_{family}_{route.get('source_id')}_{len(target)+1}",
                                "time_band": band_id,
                                "target_state": state,
                                "target_locality": locality,
                                "term_family": family,
                                "term": term,
                                "route_id": route.get("source_id"),
                                "source_id": route.get("source_id"),
                                "source_name": route.get("source_name"),
                                "route_family": route_family,
                                "source_tier": route.get("source_tier"),
                                "access_method": route.get("access_method"),
                                "collection_mode": mode,
                                "query_string": query,
                                "should_fetch": should_fetch,
                                "should_manual_review": should_manual,
                                "ethics_risk": ethics,
                                "sample_weight": score_row(state, band_id, route),
                                "sample_reason": reason,
                            }
                            target.append(row)
    return select_balanced(auto_rows, max_automated), select_balanced(manual_rows, max_manual)


def score_row(state: str, band: str, route: dict[str, Any]) -> int:
    score = 0
    if state in PRIORITY_STATES:
        score += 50
    if band in TARGET_BANDS:
        score += 30
    if route.get("source_tier") == "A":
        score += 20
    elif route.get("source_tier") in {"B", "C"}:
        score += 10
    if route.get("route_family") == "broadcast_catalogue":
        score += 10
    return score


def sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (-int(row["sample_weight"]), row["target_state"], row["time_band"], row["route_family"], row["query_id"]))


def select_balanced(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    sorted_all = sorted_rows(rows)
    for state in ["WA", "SA", "NT", "TAS", "ACT"]:
        for band in ["1955_1964", "1965_1976"]:
            for row in sorted_all:
                if row not in selected and row["target_state"] == state and row["time_band"] == band:
                    selected.append(row)
                    break
    for row in sorted_all:
        if len(selected) >= limit:
            break
        if row not in selected:
            selected.append(row)
    return selected[:limit]


def write_report(path: Path, auto: list[dict[str, Any]], manual: list[dict[str, Any]]) -> None:
    state_counts = Counter(row["target_state"] for row in auto)
    band_counts = Counter(row["time_band"] for row in auto)
    route_counts = Counter(row["route_family"] for row in auto)
    manual_sensitive = sum(1 for row in manual if row["should_manual_review"] == "true")
    lines = [
        "# Late Gap 1955-1976 Institutional Probe Plan",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Automated metadata/official-search rows: `{len(auto)}`",
        f"- Manual review rows: `{len(manual)}`",
        f"- Manual-only sensitive rows: `{manual_sensitive}`",
        "",
        "## Why This Exists Separately From Trove",
        "- The first Trove plan covers only the available 1926-1954 sampled rows.",
        "- 1955-1976 needs institutional, local-history, catalogue, heritage, and broadcast routes.",
        "- This plan is metadata-only or official-search-page only; it does not download PDFs or extract copyrighted full text.",
        "",
        "## Automated Coverage By State",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in state_counts.most_common()] or ["- None"])
    lines.extend(["", "## Automated Coverage By Time Band"])
    lines.extend([f"- `{key}`: {count}" for key, count in band_counts.most_common()] or ["- None"])
    lines.extend(["", "## Route Families"])
    lines.extend([f"- `{key}`: {count}" for key, count in route_counts.most_common()] or ["- None"])
    lines.extend(
        [
            "",
            "## Next Command",
            "```bash",
            "python3 scripts/probe_public_sources.py --db data/processed/australian_humanoid_figures.sqlite --registry config/source_registry.yml --query-plan data/interim/collection_plans/late_gap_1955_1976_institutional_probe_plan.csv --run-id late_gap_1955_1976_dry_run --limit 150 --dry-run",
            "```",
            "",
            "Execute only after reviewing route terms:",
            "```bash",
            "python3 scripts/probe_public_sources.py --db data/processed/australian_humanoid_figures.sqlite --registry config/source_registry.yml --query-plan data/interim/collection_plans/late_gap_1955_1976_institutional_probe_plan.csv --run-id late_gap_1955_1976_batch_001 --limit 150 --execute",
            "```",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--manual-out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-automated", type=int, default=150)
    parser.add_argument("--max-manual", type=int, default=300)
    args = parser.parse_args()
    del args.targets
    auto, manual = build_rows(Path(args.matrix), Path(args.registry), args.max_automated, args.max_manual)
    write_csv(Path(args.out), auto, FIELDS)
    write_csv(Path(args.manual_out), manual, FIELDS)
    write_report(Path(args.report), auto, manual)
    print(f"Wrote automated late-gap plan rows: {len(auto)}")
    print(f"Wrote manual late-gap plan rows: {len(manual)}")


if __name__ == "__main__":
    main()
