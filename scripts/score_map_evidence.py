#!/usr/bin/env python3
"""Score only true frontend-public map rows as public map evidence risks."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import normalize_space, now_iso, write_csv


VALID_STATES = {"NSW", "QLD", "VIC", "WA", "SA", "TAS", "NT", "ACT"}
INVALID_LOCATION_ROLES = {
    "publication_place",
    "publication_location",
    "archive_custody",
    "archive_custody_location",
    "institution_address",
    "source_institution_address",
    "author_residence",
    "state_only",
    "state_only_location",
    "broad_region",
    "broad_cultural_region",
    "source_collection_location",
    "cultural_association_region",
    "uncertain_or_broad_location",
}
NONPUBLIC_LABELS = {
    "INTERNAL_LOCATION_ROW",
    "CANDIDATE_LOCATION_ROW",
    "GEOCODE_REVIEW_ROW",
    "LEGACY_NONPUBLIC_LOCATION",
    "DUPLICATE_LOCATION_ROW",
    "SUPPRESSED_LOCATION_ROW",
}
FIELDS = [
    "record_id",
    "narrative_unit_id",
    "legacy_map_id",
    "frontend_join_key",
    "partition_label",
    "canonical_public_map",
    "title",
    "date_published",
    "source_name",
    "source_url",
    "current_lat",
    "current_lng",
    "current_state",
    "source_stated_place_text",
    "location_role",
    "coordinate_precision",
    "geocode_confidence",
    "review_status",
    "ethics_flags_json",
    "map_evidence_score",
    "hard_fail_reasons",
    "machine_bucket",
    "machine_recommendation",
    "machine_confidence",
    "auto_apply_eligible",
    "reviewer_decision",
    "reviewer_notes",
]


def coordinates_inside_australia(lat: Any, lng: Any) -> bool:
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    return -44.5 <= lat_f <= -9.0 and 112.0 <= lng_f <= 154.5


def has_numeric_coordinates(row: dict[str, Any]) -> bool:
    try:
        float(row.get("current_lat"))
        float(row.get("current_lng"))
        return True
    except (TypeError, ValueError):
        return False


def canonical_keys(row: dict[str, Any]) -> set[str]:
    keys = set()
    for field in ["record_id", "narrative_unit_id", "legacy_map_id", "location_id", "frontend_join_key"]:
        value = str(row.get(field) or "").strip()
        if value:
            keys.add(value)
            keys.add(f"{field}:{value}")
    return keys


def load_canonical_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ids.update(canonical_keys(row))
    return ids


def load_partition_lookup(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lookup: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for source, target in [
                ("row_id", "legacy_map_id"),
                ("narrative_unit_id", "narrative_unit_id"),
                ("record_id", "record_id"),
            ]:
                value = str(row.get(source) or "").strip()
                if value:
                    lookup.setdefault(f"{target}:{value}", row)
    return lookup


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_score_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": row.get("record_id", ""),
        "narrative_unit_id": row.get("narrative_unit_id", ""),
        "legacy_map_id": row.get("legacy_map_id", ""),
        "frontend_join_key": row.get("frontend_join_key", ""),
        "partition_label": "FRONTEND_PUBLIC_MAP",
        "title": row.get("title", ""),
        "date_published": row.get("year", ""),
        "source_name": row.get("source_name", ""),
        "source_url": row.get("source_url", ""),
        "current_lat": row.get("lat", ""),
        "current_lng": row.get("lng", ""),
        "current_state": row.get("state", ""),
        "source_stated_place_text": row.get("source_stated_place_text", ""),
        "location_role": row.get("location_role", ""),
        "coordinate_precision": row.get("coordinate_precision", ""),
        "geocode_confidence": row.get("geocode_confidence", ""),
        "review_status": row.get("review_status", ""),
        "ethics_flags_json": "",
        "reviewer_decision": "",
        "reviewer_notes": "",
    }


def partition_for_row(row: dict[str, Any], partition_lookup: dict[str, dict[str, Any]], canonical_ids: set[str]) -> str:
    for key in [f"legacy_map_id:{row.get('legacy_map_id')}", f"narrative_unit_id:{row.get('narrative_unit_id')}", f"record_id:{row.get('record_id')}"]:
        if key in partition_lookup:
            return str(partition_lookup[key].get("partition_label") or "")
    if canonical_keys(row).intersection(canonical_ids):
        return "FRONTEND_PUBLIC_MAP"
    return "HOLD_UNKNOWN_POPULATION"


def source_is_discovery_only(row: dict[str, Any]) -> bool:
    haystack = " ".join(str(row.get(k) or "") for k in ["source_name", "source_url", "ethics_flags_json"]).lower()
    return any(token in haystack for token in ["wikipedia", "openalex", "crossref", "worldcat", "open library", "paranormal", "haunted tour"])


def base_score_and_reasons(row: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    hard: list[str] = []
    place = str(row.get("source_stated_place_text") or "").strip()
    role = normalize_space(row.get("location_role"))
    state = str(row.get("jurisdiction_state") or row.get("current_state") or "").strip().upper()

    if place and place.upper() not in VALID_STATES:
        score += 20
    else:
        hard.append("missing_or_state_only_source_stated_place")

    if role:
        score += 15
        if role in INVALID_LOCATION_ROLES:
            hard.append(f"invalid_location_role:{role}")
        else:
            score += 15
    else:
        hard.append("missing_location_role")

    if coordinates_inside_australia(row.get("current_lat"), row.get("current_lng")):
        score += 15
    else:
        hard.append("coordinates_outside_australia" if has_numeric_coordinates(row) else "missing_coordinates")

    if row.get("coordinate_precision") or row.get("geocode_confidence"):
        score += 10
    else:
        hard.append("missing_coordinate_confidence")

    if state in VALID_STATES:
        score += 10
    else:
        hard.append("missing_or_invalid_jurisdiction_state")

    if row.get("review_status") and normalize_space(row.get("review_status")) not in {"rejected", "exclude"}:
        score += 10
    else:
        hard.append("missing_review_status")

    if row.get("source_url") or row.get("evidence_source_url"):
        score += 5

    if str(row.get("display_allowed") or "").strip() == "0" and row.get("display_suppression_reason"):
        hard.append("display_suppressed")

    ethics = normalize_space(row.get("ethics_flags_json"))
    if any(token in ethics for token in ["indigenous", "aboriginal", "torres", "sensitive", "restricted"]):
        if not row.get("display_decision"):
            hard.append("sensitive_without_display_decision")

    if source_is_discovery_only(row) and not row.get("evidence_source_url"):
        hard.append("discovery_only_source_as_only_evidence")
    if not place and not row.get("source_url") and not row.get("evidence_source_url"):
        hard.append("no_source_stated_place_or_evidence_url")
    return min(score, 100), hard


def score_map_row(row: dict[str, Any], canonical_ids: set[str] | None = None, partition_lookup: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    canonical_ids = canonical_ids or set()
    partition_lookup = partition_lookup or {}
    partition = row.get("partition_label") or partition_for_row(row, partition_lookup, canonical_ids)
    score, hard = base_score_and_reasons(row)
    canonical = partition == "FRONTEND_PUBLIC_MAP"

    if partition in NONPUBLIC_LABELS:
        bucket = "NONPUBLIC_IGNORE"
        confidence = 0.95
    elif partition == "UNKNOWN_MAPPED_LIKE_ROW" or partition == "HOLD_UNKNOWN_POPULATION":
        bucket = "HOLD_UNKNOWN_POPULATION"
        confidence = 0.50
    elif any(reason.startswith("invalid_location_role") for reason in hard) or "coordinates_outside_australia" in hard:
        bucket = "RED_PUBLIC_DEMOTE_ELIGIBLE"
        confidence = 0.95
    elif "display_suppressed" in hard or "sensitive_without_display_decision" in hard:
        bucket = "RED_PUBLIC_SUPPRESS_ELIGIBLE"
        confidence = 0.95
    elif score >= 85 and not hard:
        bucket = "GREEN_KEEP_PUBLIC"
        confidence = 0.90
    elif "missing_or_state_only_source_stated_place" in hard:
        bucket = "AMBER_PUBLIC_PLACE_REVIEW"
        confidence = 0.70
    elif "missing_coordinates" in hard or "missing_coordinate_confidence" in hard:
        bucket = "AMBER_PUBLIC_GEOCODE_REVIEW"
        confidence = 0.70
    elif "discovery_only_source_as_only_evidence" in hard or "no_source_stated_place_or_evidence_url" in hard:
        bucket = "AMBER_PUBLIC_SOURCE_REVIEW"
        confidence = 0.70
    else:
        bucket = "AMBER_PUBLIC_SOURCE_REVIEW"
        confidence = 0.60

    auto_apply = bucket in {"RED_PUBLIC_DEMOTE_ELIGIBLE", "RED_PUBLIC_SUPPRESS_ELIGIBLE"} and confidence >= 0.95
    return {
        "partition_label": partition,
        "canonical_public_map": "true" if canonical else "false",
        "map_evidence_score": score,
        "hard_fail_reasons": ";".join(hard),
        "machine_bucket": bucket,
        "machine_recommendation": bucket,
        "machine_confidence": f"{confidence:.2f}",
        "auto_apply_eligible": "true" if auto_apply else "false",
    }


def read_triage(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def reconciliation_resolved(path: Path) -> bool:
    if not path.exists():
        return False
    return "count_conflict_resolved: `true`" in path.read_text(encoding="utf-8")


def write_report(path: Path, rows: list[dict[str, Any]], reconciliation_path: Path) -> None:
    bucket_counts = Counter(row["machine_bucket"] for row in rows)
    hard_counts: Counter[str] = Counter()
    partition_counts = Counter(row.get("partition_label") or "unknown" for row in rows)
    public_rows = [row for row in rows if row.get("partition_label") == "FRONTEND_PUBLIC_MAP"]
    resolved = reconciliation_resolved(reconciliation_path)
    for row in rows:
        for reason in str(row.get("hard_fail_reasons") or "").split(";"):
            if reason:
                hard_counts[reason] += 1
    public_buckets = Counter(row["machine_bucket"] for row in public_rows)
    safe = resolved and any(public_buckets.get(bucket, 0) for bucket in ["RED_PUBLIC_DEMOTE_ELIGIBLE", "RED_PUBLIC_SUPPRESS_ELIGIBLE"])
    lines = [
        "# Map Evidence Machine Score Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Total scored: `{len(rows)}`",
        f"- Frontend public map rows scored: `{len(public_rows)}`",
        f"- Count conflict resolved: `{str(resolved).lower()}`",
        f"- Automatic cleanup safe: `{str(safe).lower()}`",
        "",
        "## Frontend Public Map Evidence Score",
    ]
    for key in [
        "GREEN_KEEP_PUBLIC",
        "RED_PUBLIC_DEMOTE_ELIGIBLE",
        "RED_PUBLIC_SUPPRESS_ELIGIBLE",
        "AMBER_PUBLIC_PLACE_REVIEW",
        "AMBER_PUBLIC_GEOCODE_REVIEW",
        "AMBER_PUBLIC_SOURCE_REVIEW",
    ]:
        lines.append(f"- `{key}`: {public_buckets.get(key, 0)}")
    lines.extend(["", "## Non-Public/Internal Location Rows"])
    for key in ["NONPUBLIC_IGNORE", "NONPUBLIC_CLEANUP_OPTIONAL", "HOLD_UNKNOWN_POPULATION"]:
        lines.append(f"- `{key}`: {bucket_counts.get(key, 0)}")
    lines.extend(["", "## Partition Counts"])
    lines.extend([f"- `{key}`: {partition_counts[key]}" for key in sorted(partition_counts)] or ["- None"])
    lines.extend(["", "## Top Hard-Fail Reasons"])
    lines.extend([f"- `{key}`: {count}" for key, count in hard_counts.most_common(25)] or ["- None"])
    lines.extend(
        [
            "",
            "## Cleanup Safety",
            "- Only `RED_PUBLIC_DEMOTE_ELIGIBLE` and `RED_PUBLIC_SUPPRESS_ELIGIBLE` can ever be auto-apply eligible.",
            "- `NONPUBLIC_IGNORE` rows are internal/nonpublic rows and are not public map failures.",
            "- Cleanup still requires explicit `--execute`, a DB backup, and resolved canonical counts.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def score_file(db_path: Path, canonical_map: Path, triage_csv: Path, out_path: Path, report_path: Path) -> list[dict[str, Any]]:
    del db_path
    canonical_ids = load_canonical_ids(canonical_map)
    partition_lookup = load_partition_lookup(report_path.with_name("mapped_like_row_partition.csv"))
    rows = []
    for row in read_triage(triage_csv):
        scored = dict(row)
        partition = partition_lookup.get(f"legacy_map_id:{row.get('legacy_map_id')}") or partition_lookup.get(f"narrative_unit_id:{row.get('narrative_unit_id')}") or partition_lookup.get(f"record_id:{row.get('record_id')}") or {}
        if partition.get("frontend_join_key"):
            scored["frontend_join_key"] = partition["frontend_join_key"]
        scored.update(score_map_row(row, canonical_ids, partition_lookup))
        rows.append(scored)
    represented_public_keys = {
        str(row.get("frontend_join_key") or "")
        for row in rows
        if row.get("partition_label") == "FRONTEND_PUBLIC_MAP" and row.get("frontend_join_key")
    }
    for canonical in read_csv_rows(canonical_map):
        key = str(canonical.get("frontend_join_key") or "")
        if key and key not in represented_public_keys:
            scored = canonical_score_row(canonical)
            scored.update(score_map_row(scored, canonical_ids, {}))
            rows.append(scored)
    write_csv(out_path, rows, FIELDS)
    write_report(report_path, rows, report_path.with_name("canonical_count_reconciliation.md"))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--canonical-map", required=True)
    parser.add_argument("--triage-csv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    rows = score_file(Path(args.db), Path(args.canonical_map), Path(args.triage_csv), Path(args.out), Path(args.report))
    print(f"Scored {len(rows)} map evidence rows.")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
