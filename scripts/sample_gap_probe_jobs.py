#!/usr/bin/env python3
"""Sample a high-value, small probe batch from the full gap query matrix."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_registry, load_yaml, normalize_space, source_lookup, write_csv


PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
LOWER_PRIORITY_STATES = {"NSW", "QLD", "VIC"}
INSTITUTIONAL_1955_ROUTES = {
    "state_library_catalogue",
    "state_archive_catalogue",
    "local_history_serial",
    "council_local_studies",
    "broadcast_catalogue",
    "museum_heritage_page",
}

APPENDED_FIELDS = [
    "sample_weight",
    "sample_reason",
    "collection_mode",
    "route_safety_class",
    "should_fetch",
    "should_manual_review",
    "route_source_tier",
]


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def route_without_allowed_access(route: dict[str, Any]) -> bool:
    access = normalize_space(route.get("access_method"))
    if not (route.get("base_url") or route.get("search_url_template")):
        return True
    if "manual" in access:
        return False
    allowed = {"api", "public_html", "catalogue_manual_or_html", "metadata_api", "api_or_public_html"}
    return access not in allowed


def is_automated_fetch_route(route: dict[str, Any]) -> bool:
    return (
        route.get("source_id") == "trove_newspapers_gazettes"
        and route.get("evidence_or_discovery") == "evidence_possible"
        and normalize_space(route.get("access_method")) == "api"
    )


def route_safety_class(route: dict[str, Any]) -> str:
    mode = route.get("evidence_or_discovery")
    if mode == "manual_only_sensitive":
        return "manual_sensitive"
    if mode == "discovery_only":
        return "discovery_only"
    if route_without_allowed_access(route):
        return "blocked_no_clear_official_path"
    if is_automated_fetch_route(route):
        return "automated_metadata_api"
    return "semi_automated_metadata_review"


def score_query(row: dict[str, Any], route: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if row["target_state"] in PRIORITY_STATES:
        score += 50
        reasons.append("priority_state")
    if row["time_band"] in {"1926_1939", "1940_1954", "1955_1964", "1965_1976"}:
        score += 30
        reasons.append("temporal_gap")
    if row["time_band"] in {"1955_1964", "1965_1976"} and route.get("route_family") in INSTITUTIONAL_1955_ROUTES:
        score += 25
        reasons.append("post_1955_institutional_route")
    if route.get("source_tier") == "A":
        score += 20
        reasons.append("tier_A")
    elif route.get("source_tier") in {"B", "C"}:
        score += 15
        reasons.append("tier_BC")
    if route.get("mappability_likelihood") == "high":
        score += 15
        reasons.append("high_mappability")
    elif route.get("mappability_likelihood") == "medium":
        score += 8
        reasons.append("medium_mappability")
    if row["target_state"] in LOWER_PRIORITY_STATES:
        score -= 50
        reasons.append("lower_priority_state")
    if route.get("evidence_or_discovery") == "discovery_only":
        score -= 100
        reasons.append("discovery_only_excluded")
    if route.get("evidence_or_discovery") == "manual_only_sensitive":
        score -= 100
        reasons.append("manual_sensitive_excluded_from_fetch")
    if route_without_allowed_access(route):
        score -= 100
        reasons.append("no_clear_official_path")
    return score, reasons


def source_ids_for_row(row: dict[str, Any]) -> list[str]:
    try:
        ids = json.loads(row.get("preferred_source_ids_json") or "[]")
    except json.JSONDecodeError:
        ids = []
    return [str(source_id) for source_id in ids]


def expand_jobs(query_rows: list[dict[str, str]], registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = source_lookup(registry)
    jobs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for row in query_rows:
        for source_id in source_ids_for_row(row):
            route = sources.get(source_id)
            if not route:
                continue
            key = (
                source_id,
                row.get("query_string", ""),
                row.get("target_state", ""),
                row.get("target_locality", ""),
                row.get("time_band", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            score, reasons = score_query(row, route)
            safety = route_safety_class(route)
            should_fetch = safety == "automated_metadata_api"
            should_manual = safety in {"manual_sensitive", "semi_automated_metadata_review"} or route.get("evidence_or_discovery") == "manual_only_sensitive"
            job = dict(row)
            job["preferred_source_ids_json"] = json.dumps([source_id], ensure_ascii=False)
            job.update(
                {
                    "sample_weight": score,
                    "sample_reason": ";".join(reasons),
                    "collection_mode": "automated_metadata" if should_fetch else ("manual_review" if should_manual else "excluded"),
                    "route_safety_class": safety,
                    "should_fetch": bool_text(should_fetch),
                    "should_manual_review": bool_text(should_manual),
                    "route_source_tier": route.get("source_tier") or "",
                }
            )
            jobs.append(job)
    return jobs


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def manual_out_path(out_path: Path) -> Path:
    name = out_path.name
    if "probe_batch" in name:
        name = name.replace("probe_batch", "manual_review_batch")
    else:
        name = "gap_manual_review_batch_001.csv"
    return out_path.with_name(name)


def sample_jobs(
    query_plan_path: Path,
    registry_path: Path,
    targets_path: Path,
    out_path: Path,
    batch_size: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    query_rows, original_fields = read_csv(query_plan_path)
    registry = load_registry(registry_path)
    load_yaml(targets_path)  # Validates presence for command symmetry and future target-aware scoring.
    rng = random.Random(seed)
    jobs = expand_jobs(query_rows, registry)
    for job in jobs:
        job["_tie"] = rng.random()
    automated_candidates = [
        job
        for job in jobs
        if job["should_fetch"] == "true"
        and job["route_safety_class"] != "discovery_only"
        and "manual_sensitive" not in job["route_safety_class"]
        and "no_clear_official_path" not in job["sample_reason"]
    ]
    automated = sorted(automated_candidates, key=lambda job: (-int(job["sample_weight"]), job["_tie"], job["query_id"]))[:batch_size]
    manual = sorted(
        [job for job in jobs if job["should_manual_review"] == "true"],
        key=lambda job: (-int(job["sample_weight"]), job["_tie"], job["query_id"]),
    )[:batch_size]
    fields = original_fields + [field for field in APPENDED_FIELDS if field not in original_fields]
    for job in automated + manual:
        job.pop("_tie", None)
    write_csv(out_path, automated, fields)
    write_csv(manual_out_path(out_path), manual, fields)
    return automated, manual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-plan", required=True, help="full query matrix CSV")
    parser.add_argument("--registry", required=True, help="source_registry.yml")
    parser.add_argument("--targets", required=True, help="collection_targets.yml")
    parser.add_argument("--out", required=True, help="automated batch CSV")
    parser.add_argument("--batch-size", type=int, default=300, help="number of automated jobs")
    parser.add_argument("--seed", type=int, default=42, help="deterministic sampling seed")
    args = parser.parse_args()

    automated, manual = sample_jobs(
        Path(args.query_plan),
        Path(args.registry),
        Path(args.targets),
        Path(args.out),
        args.batch_size,
        args.seed,
    )
    print(f"Wrote automated batch rows: {len(automated)} -> {args.out}")
    print(f"Wrote manual review batch rows: {len(manual)} -> {manual_out_path(Path(args.out))}")


if __name__ == "__main__":
    main()
