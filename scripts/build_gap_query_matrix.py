#!/usr/bin/env python3
"""Build the 1926-1976 collection-expansion query matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import (
    load_registry,
    load_yaml,
    make_query,
    now_iso,
    route_is_manual_only,
    routes_by_family_and_state,
    stable_query_id,
    write_csv,
)


FIELDNAMES = [
    "query_id",
    "time_band",
    "start_year",
    "end_year",
    "target_state",
    "target_state_priority",
    "target_locality",
    "term_family",
    "term",
    "query_string",
    "route_family",
    "preferred_source_ids_json",
    "trove_preferred",
    "ethics_risk",
    "review_mode",
    "expected_value_temporal",
    "expected_value_regional",
    "created_at",
]

ROUTE_FAMILY_ALIASES = {
    "trove_gazette_metadata": ["trove_newspaper_metadata"],
}


def period_key(time_band: dict[str, Any]) -> str:
    return f"{time_band['start_year']}-{time_band['end_year']}"


def route_families_for_band(time_band: dict[str, Any], targets: dict[str, Any]) -> list[str]:
    target = targets.get("period_targets", {}).get(period_key(time_band), {})
    families = list(target.get("preferred_route_families") or [])
    if not families:
        families = ["trove_newspaper_metadata"] if time_band.get("trove_preferred") else ["state_library_catalogue"]
    return families


def matching_sources(
    family: str,
    state: str,
    lookup: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    sources = list(lookup.get((family, state), []))
    for alias in ROUTE_FAMILY_ALIASES.get(family, []):
        sources.extend(lookup.get((alias, state), []))
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for source in sources:
        source_id = str(source["source_id"])
        if source_id not in seen:
            seen.add(source_id)
            deduped.append(source)
    return deduped


def value_summary(sources: list[dict[str, Any]], field: str) -> str:
    values = sorted({str(source.get(field) or "") for source in sources if source.get(field)})
    return ";".join(values)


def review_mode_for(ethics_risk: str, sources: list[dict[str, Any]]) -> str:
    if ethics_risk in {"medium_high", "high"}:
        return "manual_sensitive_review"
    if any(route_is_manual_only(source) for source in sources):
        return "manual_sensitive_review"
    return "standard_metadata_review"


def sorted_states(matrix: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        matrix.get("states", {}).items(),
        key=lambda item: (int(item[1].get("priority", 99)), item[0]),
    )


def searchable_term_families(matrix: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (name, config)
        for name, config in matrix.get("term_families", {}).items()
        if name != "context_filter_exclusions"
    ]


def build_queries(matrix: dict[str, Any], registry: list[dict[str, Any]], targets: dict[str, Any]) -> list[dict[str, Any]]:
    lookup = routes_by_family_and_state(registry)
    created_at = now_iso()
    rows: list[dict[str, Any]] = []
    for time_band in matrix.get("time_bands", []):
        families = route_families_for_band(time_band, targets)
        for state, state_config in sorted_states(matrix):
            localities = list(state_config.get("locality_terms") or [])
            locality_order = localities + [""]
            for term_family, term_config in searchable_term_families(matrix):
                ethics_risk = str(term_config.get("ethics_risk") or "medium")
                for term in term_config.get("terms", []):
                    for locality in locality_order:
                        for route_family in families:
                            sources = matching_sources(route_family, state, lookup)
                            trove = route_family.startswith("trove")
                            query_string = make_query(
                                str(term),
                                str(locality) or None,
                                state,
                                int(time_band["start_year"]),
                                int(time_band["end_year"]),
                                trove=trove,
                            )
                            source_ids = [source["source_id"] for source in sources]
                            row = {
                                "query_id": stable_query_id(
                                    time_band.get("id"),
                                    state,
                                    locality,
                                    term_family,
                                    term,
                                    route_family,
                                    query_string,
                                ),
                                "time_band": time_band["id"],
                                "start_year": int(time_band["start_year"]),
                                "end_year": int(time_band["end_year"]),
                                "target_state": state,
                                "target_state_priority": int(state_config.get("priority", 99)),
                                "target_locality": locality,
                                "term_family": term_family,
                                "term": term,
                                "query_string": query_string,
                                "route_family": route_family,
                                "preferred_source_ids_json": json.dumps(source_ids, ensure_ascii=False),
                                "trove_preferred": bool(time_band.get("trove_preferred")),
                                "ethics_risk": ethics_risk,
                                "review_mode": review_mode_for(ethics_risk, sources),
                                "expected_value_temporal": value_summary(sources, "temporal_gap_value"),
                                "expected_value_regional": value_summary(sources, "regional_balance_value"),
                                "created_at": created_at,
                            }
                            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, help="query_matrix_1926_1976.yml path")
    parser.add_argument("--registry", required=True, help="source_registry.yml path")
    parser.add_argument("--targets", required=True, help="collection_targets.yml path")
    parser.add_argument("--out", required=True, help="CSV output path")
    args = parser.parse_args()

    matrix = load_yaml(Path(args.matrix)) or {}
    registry = load_registry(Path(args.registry))
    targets = load_yaml(Path(args.targets)) or {}
    rows = build_queries(matrix, registry, targets)
    write_csv(Path(args.out), rows, FIELDNAMES)
    print(f"Wrote {len(rows)} query rows: {args.out}")


if __name__ == "__main__":
    main()
