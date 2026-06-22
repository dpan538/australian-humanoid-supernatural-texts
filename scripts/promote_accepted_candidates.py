#!/usr/bin/env python3
"""Promote accepted V2 staging candidates into canonical public records."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import utc_now_iso
from aus_humanoid.v2_schema import V2_INDEX_STATEMENTS, V2_SCHEMA_STATEMENTS


PROMOTION_VERSION = "003_promote_accepted_candidates"
PROMOTION_NAME = "Promote accepted collection candidates into canonical records"

STATE_BOUNDS = {
    "WA": (-35.5, -13.0, 112.0, 129.1),
    "NT": (-26.2, -10.5, 129.0, 138.1),
    "SA": (-38.2, -26.0, 129.0, 141.1),
    "QLD": (-29.3, -9.0, 138.0, 154.5),
    "NSW": (-37.6, -28.0, 141.0, 153.8),
    "VIC": (-39.3, -33.8, 140.8, 150.1),
    "TAS": (-44.1, -39.0, 143.5, 148.6),
    "ACT": (-35.95, -35.1, 148.7, 149.5),
}

STATE_NAMES = {
    "western australia": "WA",
    "northern territory": "NT",
    "south australia": "SA",
    "queensland": "QLD",
    "new south wales": "NSW",
    "victoria": "VIC",
    "tasmania": "TAS",
    "australian capital territory": "ACT",
}


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"\b(1[6-9]\d{2}|20\d{2})\b", str(value))
    if not match:
        return None
    return int(match.group(1))


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def source_base_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    if not parts.netloc:
        return None
    return f"{parts.scheme or 'https'}://{parts.netloc.lower()}"


def state_from_text_or_coordinates(text: str | None, latitude: float | None, longitude: float | None) -> str | None:
    normalized = f" {canonicalise_whitespace(text).lower()} "
    for state_name, code in STATE_NAMES.items():
        if state_name in normalized:
            return code
    for code in STATE_BOUNDS:
        if f" {code.lower()} " in normalized:
            return code
    if latitude is None or longitude is None:
        return None
    for code, (min_lat, max_lat, min_lon, max_lon) in STATE_BOUNDS.items():
        if min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon:
            return code
    return None


def ensure_schema(conn: sqlite3.Connection) -> None:
    for statement in V2_SCHEMA_STATEMENTS:
        conn.execute(statement)
    for statement in V2_INDEX_STATEMENTS:
        conn.execute(statement)
    conn.execute(
        """
        INSERT INTO schema_migrations(version, name, applied_at, reversible, notes)
        VALUES (?, ?, ?, 0, ?)
        ON CONFLICT(version) DO UPDATE SET
            name=excluded.name,
            notes=excluded.notes
        """,
        (
            PROMOTION_VERSION,
            PROMOTION_NAME,
            utc_now_iso(),
            "Additive promotion path; staging candidates remain auditable.",
        ),
    )


def get_or_create_source(conn: sqlite3.Connection, row: sqlite3.Row, now: str) -> int:
    source_name = row["source_name"] or row["publication_or_organisation"] or "Unspecified public source"
    source_type = row["source_type"] or "public_web"
    existing = conn.execute(
        """
        SELECT source_id
        FROM sources
        WHERE source_name = ? AND source_type = ?
        ORDER BY source_id
        LIMIT 1
        """,
        (source_name, source_type),
    ).fetchone()
    if existing:
        return int(existing["source_id"])
    conn.execute(
        """
        INSERT INTO sources(source_name, source_type, base_url, access_method, publicness_level, ethics_notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            source_name,
            source_type,
            source_base_url(row["canonical_url"] or row["url"]),
            "public_web_or_manual_verified",
            row["publicness_status"] or "public",
            row["ethics_review_status"] or "public_context_reviewed",
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def get_or_create_collection_run(conn: sqlite3.Connection, run_id: str, now: str) -> int:
    existing = conn.execute(
        "SELECT collection_run_id FROM collection_runs WHERE run_name = ? ORDER BY collection_run_id LIMIT 1",
        (run_id,),
    ).fetchone()
    if existing:
        return int(existing["collection_run_id"])
    conn.execute(
        """
        INSERT INTO collection_runs(run_name, run_started_at, run_finished_at, scope_notes, methods, limitations)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now,
            now,
            "Accepted V2 staging candidates promoted into canonical records.",
            "Idempotent promotion from collection_candidates_v2 to records/source_items/narrative tables.",
            "Candidate review evidence is preserved; map display remains derived from eligible representative locations.",
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def get_or_create_location(conn: sqlite3.Connection, row: sqlite3.Row) -> int | None:
    place_name = canonicalise_whitespace(row["location_text"])
    if not place_name:
        return None
    latitude = safe_float(row["latitude"])
    longitude = safe_float(row["longitude"])
    state = state_from_text_or_coordinates(place_name, latitude, longitude)
    existing = conn.execute("SELECT location_id FROM locations WHERE place_name = ?", (place_name,)).fetchone()
    if existing:
        location_id = int(existing["location_id"])
        if latitude is not None and longitude is not None:
            conn.execute(
                """
                UPDATE locations
                SET latitude = COALESCE(latitude, ?),
                    longitude = COALESCE(longitude, ?),
                    state_territory = COALESCE(state_territory, ?),
                    location_type = COALESCE(location_type, ?),
                    geocode_source = COALESCE(geocode_source, ?),
                    verification_status = COALESCE(verification_status, ?)
                WHERE location_id = ?
                """,
                (
                    latitude,
                    longitude,
                    state,
                    row["location_precision"],
                    row["geocode_source"],
                    row["geocode_verification_status"],
                    location_id,
                ),
            )
        return location_id
    conn.execute(
        """
        INSERT INTO locations(
            place_name, state_territory, country, latitude, longitude,
            location_type, geocode_source, verification_status, notes
        )
        VALUES (?, ?, 'Australia', ?, ?, ?, ?, ?, ?)
        """,
        (
            place_name,
            state,
            latitude,
            longitude,
            row["location_precision"],
            row["geocode_source"],
            row["geocode_verification_status"],
            row["coordinate_evidence_note"],
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def insert_source_item(conn: sqlite3.Connection, row: sqlite3.Row, record_id: int, source_id: int, now: str) -> int:
    existing = conn.execute(
        "SELECT source_item_id FROM source_items WHERE legacy_record_id = ? ORDER BY source_item_id LIMIT 1",
        (record_id,),
    ).fetchone()
    if existing:
        return int(existing["source_item_id"])
    external_id = row["external_id"] or f"candidate-v2:{row['candidate_id']}"
    conn.execute(
        """
        INSERT INTO source_items(
            legacy_record_id, source_id, external_id, title, publication_or_organisation,
            publication_date_text, publication_date_start, publication_date_precision,
            access_date, url, canonical_url, source_type, source_tier, source_mediation,
            publicness_status, rights_access_status, reproduction_status,
            text_or_ocr_status, source_traceability_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            source_id,
            external_id,
            row["title"],
            row["publication_or_organisation"] or row["source_name"],
            row["publication_date_text"],
            str(safe_int(row["publication_date_text"]) or "") or None,
            "year" if safe_int(row["publication_date_text"]) else "unknown",
            row["access_date"],
            row["url"],
            row["canonical_url"] or row["url"],
            row["source_type"],
            row["source_tier"],
            "public_candidate_review",
            row["publicness_status"] or "public",
            row["rights_access_status"] or "public_access_note_required",
            "metadata_or_short_excerpt_only",
            "public_summary_or_excerpt",
            "stable_public_url_or_identifier",
            now,
            now,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def insert_narrative(conn: sqlite3.Connection, row: sqlite3.Row, source_item_id: int, now: str) -> int:
    migration_key = f"candidate:{row['candidate_id']}"
    existing = conn.execute(
        "SELECT narrative_id FROM narrative_units WHERE migration_key = ?",
        (migration_key,),
    ).fetchone()
    if existing:
        return int(existing["narrative_id"])
    year = safe_int(row["publication_date_text"])
    conn.execute(
        """
        INSERT INTO narrative_units(
            migration_key, narrative_type, secondary_role, working_title, public_summary,
            narrative_status, analysis_status, humanoid_basis, australia_relation,
            earliest_attestation_start, earliest_attestation_precision,
            cultural_sensitivity, ethics_review_status, display_mode,
            classification_confidence, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            migration_key,
            row["narrative_type"],
            row["secondary_role"],
            row["title"],
            row["evidence_summary"],
            "accepted_public_record",
            "display_ready_reviewed",
            row["humanoid_basis"],
            row["australian_relation"],
            str(year) if year else None,
            "year" if year else "unknown",
            row["cultural_sensitivity"],
            row["ethics_review_status"],
            "summary_only" if row["cultural_sensitivity"] in {"high", "very_high"} else "full",
            row["quality_class"] or "reviewed",
            now,
            now,
        ),
    )
    narrative_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.execute(
        """
        INSERT OR IGNORE INTO narrative_source_links(
            narrative_id, source_item_id, relationship_type, confidence,
            evidence_note, human_review_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            narrative_id,
            source_item_id,
            "original_publication",
            row["quality_class"] or "reviewed",
            row["evidence_summary"],
            "accepted_candidate_reviewed",
            now,
            now,
        ),
    )
    if canonicalise_whitespace(row["source_label"]):
        conn.execute(
            """
            INSERT OR IGNORE INTO entity_labels(
                source_item_id, narrative_id, label_text, normalized_text,
                label_type, supplied_by, source_context, normalization_status, review_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_item_id,
                narrative_id,
                row["source_label"],
                canonicalise_whitespace(row["source_label"]).lower(),
                "source_or_institution_label",
                "candidate_review",
                row["evidence_summary"],
                "unresolved_public_label",
                "accepted_candidate_reviewed",
            ),
        )
    return narrative_id


def insert_record(conn: sqlite3.Connection, row: sqlite3.Row, source_id: int, now: str) -> int:
    external_id = row["external_id"] or f"candidate-v2:{row['candidate_id']}"
    year = safe_int(row["publication_date_text"])
    raw_metadata = {
        "candidate_id": row["candidate_id"],
        "run_id": row["run_id"],
        "raw_metadata_json": row["raw_metadata_json"],
        "promotion_source": "collection_candidates_v2",
    }
    conn.execute(
        """
        INSERT INTO records(
            source_id, external_id, title, publication, date_published, year,
            url, snippet, raw_metadata_json, access_status, publicness_level,
            ingestion_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            external_id,
            row["title"],
            row["publication_or_organisation"] or row["source_name"],
            row["publication_date_text"],
            year,
            row["url"],
            row["evidence_summary"],
            json.dumps(raw_metadata, ensure_ascii=False, sort_keys=True),
            row["rights_access_status"],
            row["publicness_status"] or "public",
            "accepted_candidate_promoted",
            now,
            now,
        ),
    )
    record_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.execute(
        """
        INSERT INTO coding(
            record_id, canonical_figure_guess, figure_name_as_printed,
            ontology_code, humanoid_degree_code, source_voice, genre,
            publicness_code, relevance_code, ethics_flag, notes, coded_by, coded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            row["source_label"],
            row["source_label"],
            row["narrative_type"],
            row["humanoid_basis"],
            row["secondary_role"],
            row["source_type"],
            row["publicness_status"] or "public",
            "relevant",
            row["ethics_review_status"],
            f"Promoted from accepted candidate {row['candidate_id']}; quality {row['quality_class'] or 'reviewed'}.",
            "candidate_promotion",
            now,
        ),
    )
    return record_id


def link_location(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    record_id: int,
    source_item_id: int,
    narrative_id: int,
    now: str,
) -> None:
    location_id = get_or_create_location(conn, row)
    if location_id is None:
        return
    relation_type = row["location_role"] or "uncertain_or_broad_location"
    evidence = row["coordinate_evidence_note"] or row["evidence_summary"]
    confidence = row["quality_class"] or "reviewed"
    conn.execute(
        """
        INSERT OR IGNORE INTO record_locations(record_id, location_id, relation_type, evidence_text, confidence, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            location_id,
            relation_type,
            evidence,
            confidence,
            f"Promoted from accepted candidate {row['candidate_id']}; representative map eligibility is exporter-derived.",
        ),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO narrative_locations(
            narrative_id, location_id, source_item_id, location_role,
            location_text_as_printed, location_precision, verification_status,
            confidence, evidence_excerpt, review_status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            narrative_id,
            location_id,
            source_item_id,
            relation_type,
            row["location_text"],
            row["location_precision"],
            row["geocode_verification_status"],
            confidence,
            evidence,
            "accepted_candidate_reviewed",
            now,
        ),
    )


def promote_candidates(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, int]:
    with connect(db_path) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM collection_candidates_v2
            WHERE candidate_status = 'accepted'
            ORDER BY candidate_id
            """
        ).fetchall()
        promoted = 0
        already_mapped = 0
        for row in rows:
            existing = conn.execute(
                "SELECT record_id FROM collection_candidate_record_mappings WHERE candidate_id = ?",
                (row["candidate_id"],),
            ).fetchone()
            if existing:
                already_mapped += 1
                continue
            now = utc_now_iso()
            source_id = get_or_create_source(conn, row, now)
            collection_run_id = get_or_create_collection_run(conn, row["run_id"], now)
            record_id = insert_record(conn, row, source_id, now)
            source_item_id = insert_source_item(conn, row, record_id, source_id, now)
            narrative_id = insert_narrative(conn, row, source_item_id, now)
            link_location(conn, row, record_id, source_item_id, narrative_id, now)
            conn.execute(
                """
                INSERT INTO collection_candidate_record_mappings(
                    candidate_id, record_id, source_item_id, narrative_id, collection_run_id,
                    promotion_status, promotion_notes, promoted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["candidate_id"],
                    record_id,
                    source_item_id,
                    narrative_id,
                    collection_run_id,
                    "promoted",
                    "Accepted candidate promoted to canonical records plane.",
                    now,
                ),
            )
            promoted += 1
        conn.commit()
    return {"accepted_candidates": len(rows), "promoted": promoted, "already_mapped": already_mapped}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    args = parser.parse_args()
    print(json.dumps(promote_candidates(args.db), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
