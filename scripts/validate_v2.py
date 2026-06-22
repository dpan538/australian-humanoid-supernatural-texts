#!/usr/bin/env python3
"""Validate V2 normalized archive invariants."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect, table_names
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso
from aus_humanoid.v2_schema import SCHEMA_VERSION, V2_TABLES


DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "validation_v2_report.md"


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def check(name: str, passed: bool, details: str = "") -> dict[str, str | bool]:
    return {"name": name, "passed": passed, "details": details}


def validate(db_path: str | Path) -> list[dict[str, str | bool]]:
    with connect(db_path) as conn:
        tables = table_names(conn)
        checks: list[dict[str, str | bool]] = []
        missing = sorted(set(V2_TABLES) - tables)
        checks.append(check("all_v2_tables_exist", not missing, ", ".join(missing)))
        if missing:
            return checks

        mapping_count = scalar(conn, "SELECT COUNT(*) FROM legacy_record_mappings")
        legacy_source_items = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM source_items si
            LEFT JOIN collection_candidate_record_mappings cm ON cm.source_item_id = si.source_item_id
            WHERE si.legacy_record_id IS NOT NULL
              AND cm.source_item_id IS NULL
            """,
        )
        legacy_mappings_without_record = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM legacy_record_mappings m
            LEFT JOIN records r ON r.record_id = m.legacy_record_id
            WHERE r.record_id IS NULL
            """,
        )
        duplicate_mappings = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
              SELECT legacy_record_id, COUNT(*) AS c
              FROM legacy_record_mappings
              GROUP BY legacy_record_id
              HAVING c > 1
            )
            """,
        )
        analysis_ready = scalar(conn, "SELECT COUNT(*) FROM narrative_units WHERE analysis_status = 'analysis_ready'")
        lead_accepted = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM collection_candidates_v2
            WHERE candidate_status = 'accepted'
              AND COALESCE(secondary_role, '') IN ('unresolved_lead', 'source_pointer', 'catalogue_metadata')
            """,
        )
        metadata_accepted = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM collection_candidates_v2
            WHERE candidate_status = 'accepted'
              AND COALESCE(source_type, '') IN ('academic_metadata')
            """,
        )
        accepted_candidates = scalar(conn, "SELECT COUNT(*) FROM collection_candidates_v2 WHERE candidate_status = 'accepted'")
        promoted_candidates = scalar(conn, "SELECT COUNT(*) FROM collection_candidate_record_mappings WHERE promotion_status = 'promoted'")
        promoted_without_record = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM collection_candidate_record_mappings m
            LEFT JOIN records r ON r.record_id = m.record_id
            WHERE r.record_id IS NULL
            """,
        )
        duplicate_urls = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
              SELECT canonical_url, COUNT(*) AS c
              FROM source_items
              WHERE COALESCE(canonical_url, '') != ''
                AND COALESCE(external_id, '') = ''
              GROUP BY canonical_url
              HAVING c > 1
              UNION ALL
              SELECT canonical_url || '#' || external_id, COUNT(*) AS c
              FROM source_items
              WHERE COALESCE(canonical_url, '') != ''
                AND COALESCE(external_id, '') != ''
              GROUP BY canonical_url, external_id
              HAVING c > 1
            )
            """,
        )
        publication_as_event = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM narrative_locations
            WHERE location_role = 'publication_location'
              AND location_role IN ('alleged_event_location', 'apparition_location')
            """,
        )
        restricted_public = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM narrative_units
            WHERE display_mode != 'suppressed'
              AND ethics_review_status IN ('restricted_exclude', 'restricted_excluded')
            """,
        )
        controls_in_core = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM legacy_record_mappings
            WHERE primary_record_role = 'control'
              AND narrative_id IN (
                SELECT narrative_id FROM narrative_units
                WHERE narrative_type IN ('encounter_account', 'apparition_account')
              )
            """
        )
        checks.extend(
            [
                check("legacy_mapping_count_matches_legacy_source_items", mapping_count == legacy_source_items, f"{mapping_count}/{legacy_source_items}"),
                check("legacy_mappings_reference_records", legacy_mappings_without_record == 0, str(legacy_mappings_without_record)),
                check("no_duplicate_legacy_mappings", duplicate_mappings == 0, str(duplicate_mappings)),
                check("accepted_candidates_promoted", promoted_candidates == accepted_candidates, f"{promoted_candidates}/{accepted_candidates}"),
                check("candidate_mappings_reference_records", promoted_without_record == 0, str(promoted_without_record)),
                check("automation_did_not_set_analysis_ready", analysis_ready == 0, str(analysis_ready)),
                check("no_leads_count_as_accepted_candidates", lead_accepted == 0, str(lead_accepted)),
                check("metadata_only_not_accepted_candidates", metadata_accepted == 0, str(metadata_accepted)),
                check("source_item_duplicate_urls_flagged", duplicate_urls == 0, str(duplicate_urls)),
                check("publication_location_not_event_location", publication_as_event == 0, str(publication_as_event)),
                check("restricted_content_absent_from_public_v2", restricted_public == 0, str(restricted_public)),
                check("controls_do_not_enter_encounter_core", controls_in_core == 0, str(controls_in_core)),
            ]
        )
    return checks


def write_report(checks: list[dict[str, str | bool]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    failed = [item for item in checks if not item["passed"]]
    lines = [
        "# V2 Validation Report",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Schema version: `{SCHEMA_VERSION}`",
        f"- Result: {'PASS' if not failed else 'FAIL'}",
        "",
        "## Checks",
    ]
    for item in checks:
        marker = "PASS" if item["passed"] else "FAIL"
        detail = f" - {item['details']}" if item.get("details") else ""
        lines.append(f"- {marker}: {item['name']}{detail}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Markdown report path")
    args = parser.parse_args()
    checks = validate(args.db)
    write_report(checks, Path(args.output))
    failed = [item for item in checks if not item["passed"]]
    print(json.dumps({"checks": len(checks), "failed": len(failed)}, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
