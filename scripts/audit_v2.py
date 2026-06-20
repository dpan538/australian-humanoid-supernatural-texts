#!/usr/bin/env python3
"""Write V2 corpus status, diversity, coverage, and ethics reports."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso
from aus_humanoid.v2_schema import SCHEMA_VERSION


REPORT_DIR = PROJECT_ROOT / "data" / "processed" / "v2"


def rows(conn: sqlite3.Connection, sql: str) -> list[sqlite3.Row]:
    return conn.execute(sql).fetchall()


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def date_band(value: str | None) -> str:
    if not value:
        return "undated / circulation period only"
    try:
        year = int(str(value)[:4])
    except ValueError:
        return "undated / circulation period only"
    if year < 1842:
        return "before 1842"
    if year <= 1875:
        return "1842-1875"
    if year <= 1918:
        return "1876-1918"
    if year <= 1945:
        return "1919-1945"
    if year <= 1969:
        return "1946-1969"
    if year <= 1999:
        return "1970-1999"
    return "2000-present"


def write_report(path: Path, title: str, sections: Iterable[tuple[str, list[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Schema version: `{SCHEMA_VERSION}`",
    ]
    for heading, items in sections:
        lines.extend(["", f"## {heading}"])
        lines.extend(items or ["- No rows."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def count_lines(conn: sqlite3.Connection, sql: str, label_field: str, count_field: str = "count") -> list[str]:
    return [f"- {row[label_field] or 'unknown'}: {row[count_field]}" for row in rows(conn, sql)]


def audit(db_path: str | Path, report_dir: Path) -> None:
    with connect(db_path) as conn:
        legacy = scalar(conn, "SELECT COUNT(*) FROM records")
        source_items = scalar(conn, "SELECT COUNT(*) FROM source_items")
        narratives = scalar(conn, "SELECT COUNT(*) FROM narrative_units")
        mappings = scalar(conn, "SELECT COUNT(*) FROM legacy_record_mappings")
        unmapped = scalar(
            conn,
            "SELECT COUNT(*) FROM records r LEFT JOIN legacy_record_mappings m ON m.legacy_record_id = r.record_id WHERE m.legacy_record_id IS NULL",
        )
        accepted_new = scalar(conn, "SELECT COUNT(*) FROM collection_candidates_v2 WHERE candidate_status = 'accepted'")
        rejected_new = scalar(conn, "SELECT COUNT(*) FROM collection_candidates_v2 WHERE candidate_status = 'rejected'")
        duplicate_new = scalar(conn, "SELECT COUNT(*) FROM collection_candidates_v2 WHERE candidate_status = 'duplicate'")
        lead_new = scalar(conn, "SELECT COUNT(*) FROM collection_candidates_v2 WHERE candidate_status = 'lead_only'")
        exclusions = scalar(conn, "SELECT COUNT(*) FROM exclusions")

        status_sections = [
            (
                "Exact Counts",
                [
                    f"- Legacy rows: {legacy}",
                    f"- Migrated source items: {source_items}",
                    f"- Migrated narrative units: {narratives}",
                    f"- Unmapped legacy rows: {unmapped}",
                    f"- Legacy mappings: {mappings}",
                    f"- New accepted source items: {accepted_new}",
                    f"- Rejected candidates: {rejected_new}",
                    f"- Duplicate candidates: {duplicate_new}",
                    f"- Leads: {lead_new}",
                    f"- Exclusions: {exclusions}",
                ],
            ),
            (
                "Counts By Source Organisation",
                count_lines(
                    conn,
                    """
                    SELECT COALESCE(publication_or_organisation, 'unknown') AS label, COUNT(*) AS count
                    FROM source_items GROUP BY label ORDER BY count DESC, label LIMIT 40
                    """,
                    "label",
                ),
            ),
            (
                "Counts By Source Tier",
                count_lines(
                    conn,
                    "SELECT COALESCE(source_tier, 'unknown') AS label, COUNT(*) AS count FROM source_items GROUP BY label ORDER BY count DESC",
                    "label",
                ),
            ),
            (
                "Counts By Narrative Type",
                count_lines(
                    conn,
                    """
                    SELECT COALESCE(narrative_type, secondary_role, 'untyped') AS label, COUNT(*) AS count
                    FROM narrative_units GROUP BY label ORDER BY count DESC
                    """,
                    "label",
                ),
            ),
            (
                "Counts By Analysis Status",
                count_lines(
                    conn,
                    "SELECT COALESCE(analysis_status, 'unknown') AS label, COUNT(*) AS count FROM narrative_units GROUP BY label ORDER BY count DESC",
                    "label",
                ),
            ),
            (
                "Counts By Ethics Status",
                count_lines(
                    conn,
                    "SELECT COALESCE(ethics_review_status, 'unknown') AS label, COUNT(*) AS count FROM narrative_units GROUP BY label ORDER BY count DESC",
                    "label",
                ),
            ),
        ]
        write_report(report_dir / "final_corpus_status.md", "V2 Final Corpus Status", status_sections)

        source_sections = [
            (
                "Source Organisations",
                count_lines(
                    conn,
                    """
                    SELECT COALESCE(publication_or_organisation, 'unknown') AS label, COUNT(*) AS count
                    FROM source_items GROUP BY label ORDER BY count DESC, label
                    """,
                    "label",
                ),
            ),
            (
                "Mediation",
                count_lines(
                    conn,
                    "SELECT COALESCE(source_mediation, 'unknown') AS label, COUNT(*) AS count FROM source_items GROUP BY label ORDER BY count DESC",
                    "label",
                ),
            ),
        ]
        write_report(report_dir / "source_diversity_audit.md", "V2 Source Diversity Audit", source_sections)

        type_sections = [
            (
                "Narrative Types",
                count_lines(
                    conn,
                    """
                    SELECT COALESCE(narrative_type, secondary_role, 'untyped') AS label, COUNT(*) AS count
                    FROM narrative_units GROUP BY label ORDER BY count DESC
                    """,
                    "label",
                ),
            )
        ]
        write_report(report_dir / "narrative_type_coverage.md", "V2 Narrative Type Coverage", type_sections)

        state_lines = count_lines(
            conn,
            """
            SELECT COALESCE(l.state_territory, 'AU_UNSPECIFIED') AS label, COUNT(DISTINCT nl.narrative_id) AS count
            FROM narrative_locations nl
            JOIN locations l ON l.location_id = nl.location_id
            GROUP BY label ORDER BY count DESC, label
            """,
            "label",
        )
        role_lines = count_lines(
            conn,
            "SELECT location_role AS label, COUNT(*) AS count FROM narrative_locations GROUP BY label ORDER BY count DESC",
            "label",
        )
        write_report(report_dir / "geographic_coverage.md", "V2 Geographic Coverage", [("States And Territories", state_lines), ("Location Roles", role_lines)])

        band_counter: Counter[str] = Counter()
        for row in rows(conn, "SELECT earliest_attestation_start FROM narrative_units"):
            band_counter[date_band(row["earliest_attestation_start"])] += 1
        temporal_lines = [f"- {key}: {band_counter[key]}" for key in [
            "before 1842",
            "1842-1875",
            "1876-1918",
            "1919-1945",
            "1946-1969",
            "1970-1999",
            "2000-present",
            "undated / circulation period only",
        ]]
        write_report(report_dir / "temporal_coverage.md", "V2 Temporal Coverage", [("Date Bands", temporal_lines)])

        ethics_sections = [
            (
                "Cultural Sensitivity",
                count_lines(
                    conn,
                    "SELECT COALESCE(cultural_sensitivity, 'unknown') AS label, COUNT(*) AS count FROM narrative_units GROUP BY label ORDER BY count DESC",
                    "label",
                ),
            ),
            (
                "Display Modes",
                count_lines(
                    conn,
                    "SELECT COALESCE(display_mode, 'unknown') AS label, COUNT(*) AS count FROM narrative_units GROUP BY label ORDER BY count DESC",
                    "label",
                ),
            ),
            (
                "Ethics Status",
                count_lines(
                    conn,
                    "SELECT COALESCE(ethics_review_status, 'unknown') AS label, COUNT(*) AS count FROM narrative_units GROUP BY label ORDER BY count DESC",
                    "label",
                ),
            ),
        ]
        write_report(report_dir / "ethics_and_sensitivity_audit.md", "V2 Ethics And Sensitivity Audit", ethics_sections)

        progress = [
            (
                "Collection 500 Progress",
                [
                    f"- Accepted net-new source items: {accepted_new}",
                    f"- Target: 500",
                    f"- Remaining: {max(0, 500 - accepted_new)}",
                    f"- Rejected candidates: {rejected_new}",
                    f"- Duplicate candidates: {duplicate_new}",
                    f"- Lead-only candidates: {lead_new}",
                    "- Metadata-only, source-pointer, duplicate, control, exclusion, and unresolved-lead rows are not counted as accepted.",
                ],
            )
        ]
        write_report(report_dir / "collection_500_progress.md", "V2 Collection 500 Progress", progress)

        cleaning = [
            (
                "Cleaning Rules Applied",
                [
                    "- Canonical URLs are generated with lower-cased hostnames and tracking parameters removed.",
                    "- Source labels are preserved in `entity_labels` and not silently normalized to Yowie.",
                    "- Source/publication metadata is separated from narrative/event fields.",
                    "- Automated migration marks records as display/review states only, never analysis-ready.",
                ],
            )
        ]
        write_report(report_dir / "data_cleaning_report.md", "V2 Data Cleaning Report", cleaning)

        dedupe = [
            (
                "Current State",
                [
                    "- Exact duplicate canonical URL detection is available through validation and review exports.",
                    "- Reprints and derivative summaries are represented with narrative_source_links rather than destructive record deletion.",
                    "- Near-duplicate review remains a human queue; no records are auto-merged on place/year alone.",
                ],
            )
        ]
        write_report(report_dir / "deduplication_report.md", "V2 Deduplication Report", dedupe)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--report-dir", default=str(REPORT_DIR), help="Report directory")
    args = parser.parse_args()
    audit(args.db, Path(args.report_dir))
    print(f"Wrote V2 audits to: {args.report_dir}")


if __name__ == "__main__":
    main()
