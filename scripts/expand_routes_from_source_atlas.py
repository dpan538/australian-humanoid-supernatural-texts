#!/usr/bin/env python3
"""Expand no-auth route seeds from the source atlas and registry."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

from lib.gap_recovery import read_yaml_rows, write_report

SAFE_FAMILIES = {
    "local_history_serial",
    "council_local_studies",
    "historical_society",
    "public_history_site",
    "broadcast_catalogue",
    "museum_collection",
    "museum_heritage_page",
    "archive_finding_aid",
    "state_archive_catalogue",
    "state_library_catalogue",
    "newsletter_archive",
    "journal_index",
    "public_pdf_index",
    "heritage_register",
}


def atlas_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(re.findall(r"`([a-zA-Z0-9_:-]+)`", path.read_text(encoding="utf-8")))


def seed_id(row: dict) -> str:
    return str(row.get("route_id") or row.get("source_id") or "")


def normalize_route(row: dict) -> dict:
    route_id = seed_id(row)
    return {
        "route_id": route_id,
        "source_id": row.get("source_id") or route_id,
        "source_name": row.get("source_name") or row.get("institution") or route_id,
        "source_tier": row.get("source_tier") or "B",
        "route_family": row.get("route_family") or "public_history_site",
        "state": (row.get("states") or [row.get("state") or "NATIONAL"])[0] if isinstance(row.get("states"), list) else row.get("state") or "NATIONAL",
        "official_url": row.get("official_url") or row.get("url") or row.get("search_url") or "",
        "evidence_or_discovery": row.get("evidence_or_discovery") or "evidence_possible",
        "access_method": row.get("access_method") or "public_web",
        "allowed_content_mode": row.get("allowed_content_mode") or "metadata_only",
        "collection_mode": row.get("collection_mode") or "metadata_first",
    }


def excluded_reason(row: dict, route_ids: set[str]) -> str:
    url = str(row.get("official_url") or row.get("url") or row.get("search_url") or "")
    if row.get("api_key_required") or ("trove" in url.lower() and "api" in url.lower()):
        return "api_or_trove_api"
    if row.get("evidence_or_discovery") == "manual_only_sensitive" or row.get("collection_mode") == "manual_sensitive_review":
        return "manual_sensitive"
    if row.get("evidence_or_discovery") == "discovery_only":
        return "discovery_or_authority_only"
    if row.get("source_tier") not in {"A", "B", "C", "D"}:
        return "tier_not_allowed"
    if row.get("source_tier") == "D" and row.get("evidence_or_discovery") != "evidence_only_if_original_source_identified":
        return "unsafe_tier_d"
    if row.get("route_family") not in SAFE_FAMILIES:
        return "route_family_not_automated"
    if route_ids and seed_id(row) not in route_ids and str(row.get("source_id") or "") not in route_ids:
        return "not_named_in_atlas_seed"
    return ""


def expand(atlas: Path, registry: Path, seeds: Path, out: Path, report: Path) -> dict[str, int]:
    ids = atlas_ids(atlas)
    existing = read_yaml_rows(seeds)
    existing_ids = {seed_id(row) for row in existing}
    registry_rows = read_yaml_rows(registry)
    added = []
    excluded = []
    for row in registry_rows:
        route = normalize_route(row)
        reason = excluded_reason(route, ids)
        if seed_id(route) in existing_ids:
            excluded.append({**route, "excluded_reason": "already_seeded"})
        elif reason:
            excluded.append({**route, "excluded_reason": reason})
        else:
            added.append(route)
    combined = existing + added
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(combined, sort_keys=False, allow_unicode=False), encoding="utf-8")
    priority_states = sorted({row.get("state") for row in added if row.get("state") in {"WA", "SA", "NT", "TAS", "ACT"}})
    write_report(
        report,
        "Source Atlas Expansion Report",
        {
            "Atlas route IDs": len(ids),
            "Existing seeds": len(existing),
            "Routes added": len(added),
            "Routes excluded": len(excluded),
            "Priority state coverage": ",".join(priority_states) or "none",
            "1955-1976 coverage estimate": "catalogues/local history/journals/archives prioritized",
            "Public records mutated": "no",
            "Map flags mutated": "no",
        },
        {"Added Routes": [f"- `{seed_id(row)}` {row.get('source_name')}" for row in added[:50]], "Excluded Sample": [f"- `{seed_id(row)}`: {row.get('excluded_reason')}" for row in excluded[:50]]},
    )
    return {"added": len(added), "excluded": len(excluded), "total": len(combined)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    print(expand(Path(args.atlas), Path(args.registry), Path(args.seeds), Path(args.out), Path(args.report)))


if __name__ == "__main__":
    main()
