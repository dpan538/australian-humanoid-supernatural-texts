#!/usr/bin/env python3
"""Triage existing public map flags against the collection-expansion map gate."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import normalize_space, now_iso, table_exists, write_csv


REVIEW_FIELDS = [
    "record_id",
    "narrative_unit_id",
    "legacy_map_id",
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
    "invalid_reason",
    "suggested_action",
    "reviewer_decision",
    "reviewer_notes",
    "corrected_source_stated_place_text",
    "corrected_location_role",
    "corrected_jurisdiction_state",
    "corrected_lat",
    "corrected_lng",
    "corrected_coordinate_precision",
    "corrected_geocode_confidence",
    "corrected_display_allowed",
    "corrected_display_suppression_reason",
]

INVALID_LOCATION_ROLES = {
    "publication_place",
    "publication_location",
    "archive_custody",
    "archive_custody_location",
    "source_collection_location",
    "institution_address",
    "source_institution_address",
    "author_residence",
    "state_only",
    "state_only_location",
    "broad_region",
    "broad_cultural_region",
    "cultural_association_region",
    "uncertain_or_broad_location",
}

STATE_NAMES = {
    "act": "australian capital territory",
    "nsw": "new south wales",
    "nt": "northern territory",
    "qld": "queensland",
    "sa": "south australia",
    "tas": "tasmania",
    "vic": "victoria",
    "wa": "western australia",
}


def has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def is_state_only(place_text: Any, state: Any) -> bool:
    place = normalize_space(place_text)
    current_state = normalize_space(state)
    if not place:
        return False
    state_name = STATE_NAMES.get(current_state, current_state)
    return place in {current_state, state_name}


def ethics_needs_display_decision(ethics_flags: Any) -> bool:
    ethics = normalize_space(ethics_flags)
    return any(token in ethics for token in ["indigenous", "aboriginal", "torres", "sensitive", "restricted"])


def classify_map_flag(row: dict[str, Any]) -> tuple[str, str]:
    reasons: list[str] = []

    if not has_value(row.get("source_stated_place_text")):
        reasons.append("missing_source_stated_place_text")
    if not has_value(row.get("location_role")):
        reasons.append("missing_location_role")
    if not has_value(row.get("jurisdiction_state") or row.get("current_state")):
        reasons.append("missing_jurisdiction_state")
    if row.get("lat") is None and row.get("current_lat") is None:
        reasons.append("missing_coordinates")
    if row.get("lng") is None and row.get("current_lng") is None:
        if "missing_coordinates" not in reasons:
            reasons.append("missing_coordinates")
    if not has_value(row.get("geocode_confidence")) and not has_value(row.get("coordinate_precision")):
        reasons.append("missing_coordinate_confidence")
    if not has_value(row.get("review_status")):
        reasons.append("missing_review_status")

    location_role = normalize_space(row.get("location_role"))
    if location_role in INVALID_LOCATION_ROLES:
        reasons.append(f"invalid_location_role:{location_role}")

    place_text = row.get("source_stated_place_text")
    state = row.get("jurisdiction_state") or row.get("current_state")
    if is_state_only(place_text, state):
        reasons.append("state_only_location")

    display_decision = normalize_space(row.get("display_decision"))
    display_allowed = row.get("display_allowed")
    if display_decision in {"suppressed", "suppress_public"} or str(display_allowed).strip() == "0":
        reasons.append("display_suppressed")

    if ethics_needs_display_decision(row.get("ethics_flags_json")) and not display_decision:
        reasons.append("sensitive_without_display_decision")

    if not reasons:
        return "keep_public_map_flag", ""

    if "sensitive_without_display_decision" in reasons:
        return "manual_sensitive_review", ";".join(reasons)
    if "display_suppressed" in reasons:
        return "suppress_public_map", ";".join(reasons)
    if any(reason.startswith("invalid_location_role") for reason in reasons) or "state_only_location" in reasons:
        return "demote_to_unmapped", ";".join(reasons)
    if "missing_source_stated_place_text" in reasons or "missing_location_role" in reasons or "missing_jurisdiction_state" in reasons:
        return "needs_place_evidence_review", ";".join(reasons)
    if "missing_coordinates" in reasons or "missing_coordinate_confidence" in reasons:
        return "needs_geocode_review", ";".join(reasons)
    return "needs_place_evidence_review", ";".join(reasons)


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def fetch_v2_map_rows(conn: sqlite3.Connection, warnings: list[str]) -> list[dict[str, Any]]:
    required = {"narrative_locations", "locations"}
    missing = sorted(table for table in required if not table_exists(conn, table))
    if missing:
        warnings.append("Missing V2 map tables: " + ", ".join(missing))
        return []
    if not table_exists(conn, "narrative_units"):
        warnings.append("Missing narrative_units; title/date/display/ethics fields will be blank.")
    if not table_exists(conn, "source_items"):
        warnings.append("Missing source_items; source fields will be blank.")

    rows = conn.execute(
        """
        SELECT
            CAST(COALESCE(m.legacy_record_id, si.legacy_record_id, '') AS TEXT) AS record_id,
            CAST(nl.narrative_id AS TEXT) AS narrative_unit_id,
            CAST(nl.narrative_location_id AS TEXT) AS legacy_map_id,
            COALESCE(nu.working_title, si.title, '') AS title,
            COALESCE(nu.earliest_attestation_start, si.publication_date_start, si.publication_date_text, '') AS date_published,
            COALESCE(si.publication_or_organisation, '') AS source_name,
            COALESCE(si.url, si.canonical_url, '') AS source_url,
            l.latitude AS current_lat,
            l.longitude AS current_lng,
            COALESCE(l.state_territory, '') AS current_state,
            COALESCE(nl.location_text_as_printed, '') AS source_stated_place_text,
            COALESCE(nl.location_role, '') AS location_role,
            COALESCE(nl.location_precision, '') AS coordinate_precision,
            COALESCE(nl.confidence, nl.verification_status, l.verification_status, '') AS geocode_confidence,
            COALESCE(nl.review_status, nl.verification_status, l.verification_status, '') AS review_status,
            COALESCE(nu.display_mode, '') AS display_decision,
            COALESCE(si.source_type, si.source_mediation, '') AS source_family,
            json_object(
                'cultural_sensitivity', COALESCE(nu.cultural_sensitivity, ''),
                'ethics_review_status', COALESCE(nu.ethics_review_status, ''),
                'display_mode', COALESCE(nu.display_mode, '')
            ) AS ethics_flags_json
        FROM narrative_locations nl
        JOIN locations l ON l.location_id = nl.location_id
        LEFT JOIN narrative_units nu ON nu.narrative_id = nl.narrative_id
        LEFT JOIN source_items si ON si.source_item_id = nl.source_item_id
        LEFT JOIN legacy_record_mappings m ON m.narrative_id = nl.narrative_id
        ORDER BY current_state, nl.narrative_id, nl.narrative_location_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_legacy_map_rows(conn: sqlite3.Connection, warnings: list[str]) -> list[dict[str, Any]]:
    required = {"record_locations", "locations", "records"}
    missing = sorted(table for table in required if not table_exists(conn, table))
    if missing:
        warnings.append("Missing legacy map tables: " + ", ".join(missing))
        return []
    rows = conn.execute(
        """
        SELECT
            CAST(r.record_id AS TEXT) AS record_id,
            '' AS narrative_unit_id,
            CAST(r.record_id || ':' || rl.location_id AS TEXT) AS legacy_map_id,
            COALESCE(r.title, '') AS title,
            COALESCE(r.date_published, CAST(r.year AS TEXT), '') AS date_published,
            COALESCE(r.publication, '') AS source_name,
            COALESCE(r.url, '') AS source_url,
            l.latitude AS current_lat,
            l.longitude AS current_lng,
            COALESCE(l.state_territory, '') AS current_state,
            COALESCE(rl.evidence_text, '') AS source_stated_place_text,
            COALESCE(rl.relation_type, '') AS location_role,
            '' AS coordinate_precision,
            COALESCE(rl.confidence, l.verification_status, '') AS geocode_confidence,
            COALESCE(rl.confidence, l.verification_status, '') AS review_status,
            '' AS display_decision,
            '' AS source_family,
            json_object('legacy_publicness_level', COALESCE(r.publicness_level, '')) AS ethics_flags_json
        FROM record_locations rl
        JOIN records r ON r.record_id = rl.record_id
        JOIN locations l ON l.location_id = rl.location_id
        ORDER BY current_state, r.record_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def review_row(row: dict[str, Any]) -> dict[str, Any]:
    classifier_input = dict(row)
    classifier_input["lat"] = row.get("current_lat")
    classifier_input["lng"] = row.get("current_lng")
    classifier_input["jurisdiction_state"] = row.get("current_state")
    suggested_action, invalid_reason = classify_map_flag(classifier_input)
    return {
        "record_id": row.get("record_id", ""),
        "narrative_unit_id": row.get("narrative_unit_id", ""),
        "legacy_map_id": row.get("legacy_map_id", ""),
        "title": row.get("title", ""),
        "date_published": row.get("date_published", ""),
        "source_name": row.get("source_name", ""),
        "source_url": row.get("source_url", ""),
        "current_lat": row.get("current_lat", ""),
        "current_lng": row.get("current_lng", ""),
        "current_state": row.get("current_state", ""),
        "source_stated_place_text": row.get("source_stated_place_text", ""),
        "location_role": row.get("location_role", ""),
        "coordinate_precision": row.get("coordinate_precision", ""),
        "geocode_confidence": row.get("geocode_confidence", ""),
        "review_status": row.get("review_status", ""),
        "ethics_flags_json": row.get("ethics_flags_json", ""),
        "invalid_reason": invalid_reason,
        "suggested_action": suggested_action,
        "reviewer_decision": "",
        "reviewer_notes": "",
        "corrected_source_stated_place_text": "",
        "corrected_location_role": "",
        "corrected_jurisdiction_state": "",
        "corrected_lat": "",
        "corrected_lng": "",
        "corrected_coordinate_precision": "",
        "corrected_geocode_confidence": "",
        "corrected_display_allowed": "",
        "corrected_display_suppression_reason": "",
        "_source_family": row.get("source_family", ""),
    }


def write_report(path: Path, rows: list[dict[str, Any]], warnings: list[str]) -> None:
    action_counts = Counter(row["suggested_action"] for row in rows)
    reason_counts: Counter[str] = Counter()
    source_counts = Counter(str(row.get("_source_family") or "unknown") for row in rows)
    state_counts = Counter(str(row.get("current_state") or "unknown") for row in rows)
    for row in rows:
        for reason in str(row.get("invalid_reason") or "").split(";"):
            if reason:
                reason_counts[reason] += 1
    passing = action_counts.get("keep_public_map_flag", 0)
    demote = action_counts.get("demote_to_unmapped", 0)
    sensitive = action_counts.get("manual_sensitive_review", 0)

    lines = [
        "# Legacy Map Flag Triage Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Total mapped rows inspected: `{len(rows)}`",
        f"- Passing evidence gate: `{passing}`",
        f"- Suggested for demotion: `{demote}`",
        f"- Requiring sensitive review: `{sensitive}`",
        "",
        "## Suggested Actions",
    ]
    lines.extend([f"- `{key}`: {action_counts[key]}" for key in sorted(action_counts)] or ["- None"])
    lines.extend(["", "## Failing Reasons"])
    lines.extend([f"- `{key}`: {reason_counts[key]}" for key in sorted(reason_counts)] or ["- None"])
    lines.extend(["", "## Top Source Families"])
    lines.extend([f"- `{key}`: {count}" for key, count in source_counts.most_common(20)] or ["- None"])
    lines.extend(["", "## Top States"])
    lines.extend([f"- `{key}`: {count}" for key, count in state_counts.most_common(20)] or ["- None"])
    if warnings:
        lines.extend(["", "## Schema Warnings"])
        lines.extend([f"- {warning}" for warning in warnings])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def triage(db_path: Path, out_path: Path, report_path: Path) -> list[dict[str, Any]]:
    warnings: list[str] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = fetch_v2_map_rows(conn, warnings)
        if not rows:
            rows = fetch_legacy_map_rows(conn, warnings)
    review_rows = [review_row(row) for row in rows]
    write_csv(out_path, review_rows, REVIEW_FIELDS)
    write_report(report_path, review_rows, warnings)
    return review_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--out", required=True, help="CSV review output")
    parser.add_argument("--report", required=True, help="Markdown report output")
    args = parser.parse_args()

    rows = triage(Path(args.db), Path(args.out), Path(args.report))
    print(f"Inspected {len(rows)} mapped rows.")
    print(f"Wrote review CSV: {args.out}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
