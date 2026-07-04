#!/usr/bin/env python3
"""Import reviewed 1926-1976 gap candidates into the canonical V2 data plane.

This script intentionally imports only the reviewed production candidates from
the local gap overlay work. It excludes tourism-directory leads and non-strict
live metadata rows, writes a compact audit CSV, stages candidates into
collection_candidates_v2, promotes the accepted rows, and leaves frontend JSON
export to scripts/export_frontend_json.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import utc_now_iso
from aus_humanoid.v2_schema import V2_INDEX_STATEMENTS, V2_SCHEMA_STATEMENTS
from promote_accepted_candidates import (
    get_or_create_collection_run,
    get_or_create_source,
    insert_narrative,
    insert_record,
    insert_source_item,
    link_location,
)

RUN_ID = "gap_1926_1976_reviewed_import_20260704"
DEFAULT_FRONTEND_DATA = ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_AUDIT_CSV = ROOT / "data" / "processed" / "v2" / "1926_1976_reviewed_import_batch.csv"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_1976_reviewed_import_report.md"

CANDIDATE_FILES = [
    ROOT / "data" / "interim" / "gap_probe_1926_2011" / "abc_public_search" / "abc_public_search_round011_abc_place_expanded_strict_candidates.csv",
    ROOT / "data" / "interim" / "gap_probe_1926_2011" / "abc_public_search" / "abc_public_search_round012a_abc_more_pages_20q_strict_candidates.csv",
    ROOT / "data" / "interim" / "gap_probe_1926_2011" / "ayr_yowie_map" / "ayr_yowie_map_round013_candidates.csv",
    ROOT / "data" / "interim" / "gap_probe_1926_2011" / "ayr_state_indexes" / "ayr_state_indexes_round014_candidates.csv",
    ROOT / "data" / "interim" / "gap_probe_1926_2011" / "public_books_metadata" / "public_books_metadata_round017_openlibrary_strict_candidates.csv",
    ROOT / "data" / "interim" / "gap_probe_1926_2011" / "wikidata_entities" / "wikidata_entities_round023_strictest_candidates.csv",
    ROOT / "data" / "interim" / "gap_probe_1926_2011" / "public_books_metadata" / "public_books_metadata_round030_ia_1926_1976_urllib_strict_candidates.csv",
]

MAPPED_SOURCE_TYPES = {
    "public_web_yowie_report_map",
    "public_web_yowie_state_report_index",
    "institutional_media_page",
    "public_books_metadata_internet_archive",
}
RECORD_ONLY_SOURCE_TYPES = {
    "public_books_metadata_openlibrary",
    "public_wikidata_entity_metadata",
}
EXCLUDED_SOURCE_TYPES = {
    "public_web_haunted_places_directory",
    "live_crawl_openalex",
    "live_crawl_crossref",
}
EXPORTER_LOCATION_ROLES = {
    "alleged_event_location",
    "apparition_location",
    "narrative_setting",
    "legend_associated_place",
    "rumour_circulation_place",
    "reported_place",
    "source_visible_place",
    "source_visible_place_hint",
    "mentioned_place",
}
EXPORTER_LOCATION_TYPES = {"exact_site", "road_segment", "named_feature", "town", "locality", "precise_point"}
FIGURE_LABEL_NORMALISATION = {
    "yowie": "Yowie",
    "yowies": "Yowie",
    "ghosts": "ghost",
    "apparitions": "apparition",
    "fisher's_ghost": "Fisher's Ghost",
    "haunted_house": "haunted",
    "haunted_houses": "haunted",
    "haunted_places": "haunted",
    "haunted_town": "haunted",
    "hairy_man": "Hairy Man",
    "hairy_people": "Hairy Man",
    "bunyips": "bunyip",
    "yahoo": "Yahoo",
    "pangkarlangu": "Pangkarlangu",
    "mimi": "Mimi",
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def normalise_figure_label(value: Any) -> str:
    label = clean(value)
    if not label:
        return ""
    return FIGURE_LABEL_NORMALISATION.get(label.lower(), label)


def canonicalize_url(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    parts = urlsplit(value)
    scheme = parts.scheme or "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def load_frontend_duplicate_keys(path: Path) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    urls: set[str] = set()
    url_places: set[tuple[str, str]] = set()
    external_ids: set[str] = set()
    for record in data.get("records", []):
        url = canonicalize_url(record.get("url"))
        external_id = clean(record.get("external_id"))
        place = clean(record.get("map_place_name") or record.get("location_summary") or "")
        if url:
            urls.add(url)
        if external_id:
            external_ids.add(external_id)
        if url and place:
            url_places.add((url, norm(place.split(",", 1)[0].split("(", 1)[0])))
    return urls, url_places, external_ids


def existing_db_keys(conn: sqlite3.Connection, run_id: str) -> tuple[set[str], set[tuple[str, str]]]:
    url_only: set[str] = set()
    url_external: set[tuple[str, str]] = set()
    for row in conn.execute(
        """
        SELECT si.canonical_url, si.external_id
        FROM source_items si
        LEFT JOIN collection_candidate_record_mappings m ON m.source_item_id = si.source_item_id
        LEFT JOIN collection_candidates_v2 c ON c.candidate_id = m.candidate_id
        WHERE COALESCE(si.canonical_url, '') != ''
          AND COALESCE(c.run_id, '') != ?
        """
        ,
        (run_id,),
    ).fetchall():
        url = canonicalize_url(row["canonical_url"])
        external_id = clean(row["external_id"])
        if external_id:
            url_external.add((url, external_id))
        elif url:
            url_only.add(url)
    for row in conn.execute(
        """
        SELECT canonical_url, external_id
        FROM collection_candidates_v2
        WHERE candidate_status = 'accepted'
          AND COALESCE(canonical_url, '') != ''
          AND COALESCE(run_id, '') != ?
        """,
        (run_id,),
    ).fetchall():
        url = canonicalize_url(row["canonical_url"])
        external_id = clean(row["external_id"])
        if external_id:
            url_external.add((url, external_id))
        elif url:
            url_only.add(url)
    return url_only, url_external


def load_accepted_rows(paths: list[Path]) -> tuple[list[dict[str, str]], Counter[str]]:
    rows: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                status = raw.get("candidate_status") or ""
                counts[f"raw_status:{status or 'blank'}"] += 1
                source_type = raw.get("source_type") or ""
                if source_type in EXCLUDED_SOURCE_TYPES:
                    counts[f"excluded_source:{source_type}"] += 1
                    continue
                if status != "accepted" or raw.get("acceptance_decision") != "accepted":
                    continue
                url = canonicalize_url(raw.get("canonical_url") or raw.get("url"))
                place = norm(clean(raw.get("location_text")).split(",", 1)[0])
                key = (url, place or clean(raw.get("external_id")) or norm(raw.get("title") or ""))
                if key in seen:
                    counts["duplicate_within_import_files"] += 1
                    continue
                seen.add(key)
                rows.append(raw)
    return rows, counts


def row_has_coordinates(row: dict[str, str]) -> bool:
    try:
        float(row.get("latitude") or "")
        float(row.get("longitude") or "")
    except ValueError:
        return False
    return True


def normalize_for_import(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    source_type = out.get("source_type") or ""
    out["source_label"] = normalise_figure_label(out.get("source_label"))
    out["canonical_url"] = canonicalize_url(out.get("canonical_url") or out.get("url"))
    out["url"] = out["canonical_url"] or clean(out.get("url"))
    if not clean(out.get("publication_date_text")) and clean(out.get("year")):
        out["publication_date_text"] = clean(out.get("year"))
    if not clean(out.get("access_date")):
        out["access_date"] = utc_now_iso()[:10]
    if not clean(out.get("publicness_status")):
        out["publicness_status"] = "public"
    if not clean(out.get("rights_access_status")):
        out["rights_access_status"] = "public metadata or public page; no full reproduction asserted"
    if not clean(out.get("quality_class")):
        out["quality_class"] = "B" if source_type.startswith("public_web_yowie") else "C"
    if not clean(out.get("duplicate_check_status")):
        out["duplicate_check_status"] = "base_frontend_and_source_item_keys_checked"

    should_map = source_type in MAPPED_SOURCE_TYPES and row_has_coordinates(out)
    if source_type in RECORD_ONLY_SOURCE_TYPES:
        should_map = False
    if should_map:
        role = clean(out.get("location_role"))
        precision = clean(out.get("location_precision"))
        if source_type.startswith("public_web_yowie"):
            role = "source_visible_place"
            precision = "locality"
            out["geocode_verification_status"] = "verified_place"
            note = clean(out.get("coordinate_evidence_note"))
            out["coordinate_evidence_note"] = (
                f"{note} Public source marker retained as a display location only; "
                "not independent verification of claim, habitat, or population."
            ).strip()
        elif source_type == "public_books_metadata_internet_archive":
            role = "source_visible_place"
            precision = "town"
            out["geocode_verification_status"] = "verified_place"
            out["coordinate_evidence_note"] = (
                clean(out.get("coordinate_evidence_note"))
                + " Campbelltown retained as public display location for Fisher's Ghost metadata review."
            ).strip()
        else:
            if role not in EXPORTER_LOCATION_ROLES:
                role = "source_visible_place"
            if precision not in EXPORTER_LOCATION_TYPES:
                precision = "locality"
            out["geocode_verification_status"] = "verified_place"
        out["location_role"] = role
        out["location_precision"] = precision
    else:
        out["latitude"] = ""
        out["longitude"] = ""
        if source_type in RECORD_ONLY_SOURCE_TYPES:
            out["location_role"] = clean(out.get("location_role")) or "source_context_record"
            out["location_precision"] = clean(out.get("location_precision")) or "unmapped"
            out["geocode_verification_status"] = ""
            out["coordinate_evidence_note"] = clean(out.get("coordinate_evidence_note")) or "Record-only import; no independently reviewed public display location."

    out["run_id"] = RUN_ID
    out["candidate_status"] = "accepted"
    out["acceptance_decision"] = "accepted"
    out["rejection_reason"] = ""
    out["raw_metadata_json"] = out.get("raw_metadata_json") or json.dumps(row, ensure_ascii=False, sort_keys=True)
    return out


def filter_new_rows(conn: sqlite3.Connection, rows: list[dict[str, str]], frontend_path: Path, run_id: str) -> tuple[list[dict[str, str]], Counter[str]]:
    frontend_urls, frontend_url_places, frontend_external_ids = load_frontend_duplicate_keys(frontend_path)
    db_url_only, db_url_external = existing_db_keys(conn, run_id)
    kept: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for row in rows:
        normalized = normalize_for_import(row)
        url = canonicalize_url(normalized.get("canonical_url") or normalized.get("url"))
        external_id = clean(normalized.get("external_id"))
        place = norm(clean(normalized.get("location_text")).split(",", 1)[0])
        if external_id and external_id in frontend_external_ids:
            counts["duplicate_external_id_against_frontend"] += 1
            continue
        if url and place and (url, place) in frontend_url_places:
            counts["duplicate_url_place_against_frontend"] += 1
            continue
        if url and not place and url in frontend_urls:
            counts["duplicate_url_against_frontend"] += 1
            continue
        if url and external_id and (url, external_id) in db_url_external:
            counts["duplicate_url_external_against_db"] += 1
            continue
        if url and not external_id and url in db_url_only:
            counts["duplicate_url_against_db"] += 1
            continue
        kept.append(normalized)
    return kept, counts


def load_existing_run_rows(conn: sqlite3.Connection, run_id: str) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT *
        FROM collection_candidates_v2
        WHERE run_id = ?
        ORDER BY candidate_id
        """,
        (run_id,),
    ).fetchall()
    return [normalize_for_import({key: "" if row[key] is None else str(row[key]) for key in row.keys()}) for row in rows]


def ensure_schema(conn: sqlite3.Connection) -> None:
    for statement in V2_SCHEMA_STATEMENTS:
        conn.execute(statement)
    for statement in V2_INDEX_STATEMENTS:
        conn.execute(statement)


def insert_candidate(conn: sqlite3.Connection, row: dict[str, str]) -> int:
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO collection_candidates_v2(
            run_id, candidate_status, source_name, source_type, source_tier,
            title, publication_or_organisation, publication_date_text, access_date, url,
            canonical_url, external_id, publicness_status, rights_access_status,
            narrative_type, secondary_role,
            australian_relation, humanoid_basis, source_label, location_text,
            location_role, latitude, longitude, location_precision,
            geocode_source, geocode_verification_status, coordinate_evidence_note,
            duplicate_check_status, quality_class, ethics_review_status, cultural_sensitivity,
            acceptance_decision, rejection_reason, evidence_summary,
            raw_metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, canonical_url, external_id) DO UPDATE SET
            candidate_status=excluded.candidate_status,
            source_name=excluded.source_name,
            source_type=excluded.source_type,
            source_tier=excluded.source_tier,
            title=excluded.title,
            publication_or_organisation=excluded.publication_or_organisation,
            publication_date_text=excluded.publication_date_text,
            access_date=excluded.access_date,
            url=excluded.url,
            publicness_status=excluded.publicness_status,
            rights_access_status=excluded.rights_access_status,
            narrative_type=excluded.narrative_type,
            secondary_role=excluded.secondary_role,
            australian_relation=excluded.australian_relation,
            humanoid_basis=excluded.humanoid_basis,
            source_label=excluded.source_label,
            location_text=excluded.location_text,
            location_role=excluded.location_role,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            location_precision=excluded.location_precision,
            geocode_source=excluded.geocode_source,
            geocode_verification_status=excluded.geocode_verification_status,
            coordinate_evidence_note=excluded.coordinate_evidence_note,
            duplicate_check_status=excluded.duplicate_check_status,
            quality_class=excluded.quality_class,
            ethics_review_status=excluded.ethics_review_status,
            cultural_sensitivity=excluded.cultural_sensitivity,
            acceptance_decision=excluded.acceptance_decision,
            rejection_reason=excluded.rejection_reason,
            evidence_summary=excluded.evidence_summary,
            raw_metadata_json=excluded.raw_metadata_json,
            updated_at=excluded.updated_at
        """,
        (
            row.get("run_id"),
            row.get("candidate_status"),
            row.get("source_name"),
            row.get("source_type"),
            row.get("source_tier"),
            row.get("title"),
            row.get("publication_or_organisation"),
            row.get("publication_date_text"),
            row.get("access_date"),
            row.get("url"),
            row.get("canonical_url"),
            row.get("external_id"),
            row.get("publicness_status"),
            row.get("rights_access_status"),
            row.get("narrative_type"),
            row.get("secondary_role"),
            row.get("australian_relation") or row.get("australia_relation"),
            row.get("humanoid_basis"),
            row.get("source_label"),
            row.get("location_text"),
            row.get("location_role"),
            float(row["latitude"]) if clean(row.get("latitude")) else None,
            float(row["longitude"]) if clean(row.get("longitude")) else None,
            row.get("location_precision"),
            row.get("geocode_source"),
            row.get("geocode_verification_status"),
            row.get("coordinate_evidence_note"),
            row.get("duplicate_check_status"),
            row.get("quality_class"),
            row.get("ethics_review_status"),
            row.get("cultural_sensitivity"),
            row.get("acceptance_decision"),
            row.get("rejection_reason"),
            row.get("evidence_summary"),
            row.get("raw_metadata_json"),
            now,
            now,
        ),
    )
    candidate = conn.execute(
        "SELECT candidate_id FROM collection_candidates_v2 WHERE run_id = ? AND canonical_url = ? AND external_id = ?",
        (row.get("run_id"), row.get("canonical_url"), row.get("external_id")),
    ).fetchone()
    return int(candidate["candidate_id"])


def promote_run(conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT *
        FROM collection_candidates_v2
        WHERE run_id = ? AND candidate_status = 'accepted'
        ORDER BY candidate_id
        """,
        (run_id,),
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
                "Reviewed 1926-1976 gap candidate promoted to canonical records plane.",
                now,
            ),
        )
        promoted += 1
    return {"accepted_candidates": len(rows), "promoted": promoted, "already_mapped": already_mapped}


def repair_run_map_locations(conn: sqlite3.Connection, run_id: str) -> int:
    """Let reviewed import rows update older placeholder location verification.

    get_or_create_location is intentionally conservative and uses COALESCE for
    existing places. For this reviewed batch, however, a few old placeholder
    locations already exist with source_named_place_needs_geocode. If the
    candidate row carries reviewed coordinates and a normalized exporter-valid
    map role, update only locations linked to this run.
    """

    updated = conn.execute(
        """
        UPDATE locations
        SET verification_status = 'verified_place',
            location_type = CASE
                WHEN location_type NOT IN ('exact_site', 'road_segment', 'named_feature', 'town', 'locality', 'precise_point')
                THEN 'locality'
                ELSE location_type
            END,
            notes = TRIM(COALESCE(notes, '') || ' Reviewed 1926-1976 gap import retained this source-visible place as public display location only.')
        WHERE location_id IN (
            SELECT l.location_id
            FROM locations l
            JOIN record_locations rl ON rl.location_id = l.location_id
            JOIN collection_candidate_record_mappings m ON m.record_id = rl.record_id
            JOIN collection_candidates_v2 c ON c.candidate_id = m.candidate_id
            WHERE c.run_id = ?
              AND c.source_type IN ('public_web_yowie_report_map', 'public_web_yowie_state_report_index', 'institutional_media_page', 'public_books_metadata_internet_archive')
              AND c.latitude IS NOT NULL
              AND c.longitude IS NOT NULL
              AND rl.relation_type IN ('alleged_event_location', 'apparition_location', 'narrative_setting', 'legend_associated_place', 'rumour_circulation_place', 'reported_place', 'source_visible_place', 'source_visible_place_hint', 'mentioned_place')
              AND l.latitude IS NOT NULL
              AND l.longitude IS NOT NULL
              AND COALESCE(l.verification_status, '') NOT IN ('verified_place', 'verified_locality', 'verified_gazetteer_point', 'verified_institutional_coordinate')
        )
        """,
        (run_id,),
    ).rowcount
    return int(updated or 0)


def sync_promoted_run_labels(conn: sqlite3.Connection, run_id: str) -> int:
    """Keep already-promoted records aligned with import label normalization."""

    updated_coding = conn.execute(
        """
        UPDATE coding
        SET canonical_figure_guess = (
                SELECT c.source_label
                FROM collection_candidate_record_mappings m
                JOIN collection_candidates_v2 c ON c.candidate_id = m.candidate_id
                WHERE m.record_id = coding.record_id AND c.run_id = ?
            ),
            figure_name_as_printed = (
                SELECT c.source_label
                FROM collection_candidate_record_mappings m
                JOIN collection_candidates_v2 c ON c.candidate_id = m.candidate_id
                WHERE m.record_id = coding.record_id AND c.run_id = ?
            )
        WHERE record_id IN (
            SELECT m.record_id
            FROM collection_candidate_record_mappings m
            JOIN collection_candidates_v2 c ON c.candidate_id = m.candidate_id
            WHERE c.run_id = ?
              AND COALESCE(c.source_label, '') != ''
        )
        """,
        (run_id, run_id, run_id),
    ).rowcount
    updated_labels = conn.execute(
        """
        UPDATE entity_labels
        SET label_text = (
                SELECT c.source_label
                FROM collection_candidate_record_mappings m
                JOIN collection_candidates_v2 c ON c.candidate_id = m.candidate_id
                WHERE m.source_item_id = entity_labels.source_item_id
                  AND COALESCE(m.narrative_id, -1) = COALESCE(entity_labels.narrative_id, -1)
                  AND c.run_id = ?
            ),
            normalized_text = LOWER((
                SELECT c.source_label
                FROM collection_candidate_record_mappings m
                JOIN collection_candidates_v2 c ON c.candidate_id = m.candidate_id
                WHERE m.source_item_id = entity_labels.source_item_id
                  AND COALESCE(m.narrative_id, -1) = COALESCE(entity_labels.narrative_id, -1)
                  AND c.run_id = ?
            ))
        WHERE source_item_id IN (
            SELECT m.source_item_id
            FROM collection_candidate_record_mappings m
            JOIN collection_candidates_v2 c ON c.candidate_id = m.candidate_id
            WHERE c.run_id = ?
              AND COALESCE(c.source_label, '') != ''
        )
        """,
        (run_id, run_id, run_id),
    ).rowcount
    return int(updated_coding or 0) + int(updated_labels or 0)


def write_audit_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "run_id",
        "candidate_status",
        "source_name",
        "source_type",
        "source_tier",
        "title",
        "publication_or_organisation",
        "publication_date_text",
        "access_date",
        "url",
        "canonical_url",
        "external_id",
        "publicness_status",
        "rights_access_status",
        "narrative_type",
        "secondary_role",
        "australian_relation",
        "humanoid_basis",
        "source_label",
        "location_text",
        "location_role",
        "latitude",
        "longitude",
        "location_precision",
        "geocode_source",
        "geocode_verification_status",
        "coordinate_evidence_note",
        "duplicate_check_status",
        "quality_class",
        "ethics_review_status",
        "cultural_sensitivity",
        "acceptance_decision",
        "rejection_reason",
        "evidence_summary",
        "raw_metadata_json",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_report(
    path: Path,
    loaded: list[dict[str, str]],
    kept: list[dict[str, str]],
    raw_counts: Counter[str],
    duplicate_counts: Counter[str],
    promotion: dict[str, int],
    repaired_locations: int,
    synced_labels: int,
) -> None:
    source_counts = Counter(row.get("source_type") for row in kept)
    mapped_counts = Counter(row.get("source_type") for row in kept if clean(row.get("latitude")) and clean(row.get("longitude")))
    record_only = len(kept) - sum(mapped_counts.values())
    lines = [
        "# 1926-1976 Reviewed Gap Candidate Import",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Run id: `{RUN_ID}`",
        f"- Accepted rows loaded from source files: `{len(loaded)}`",
        f"- Rows kept after production duplicate filters: `{len(kept)}`",
        f"- Record-only rows: `{record_only}`",
        f"- Rows with exporter-eligible map locations: `{sum(mapped_counts.values())}`",
        f"- Promoted records this run: `{promotion['promoted']}`",
        f"- Already promoted for this run: `{promotion['already_mapped']}`",
        f"- Existing location verification rows repaired: `{repaired_locations}`",
        f"- Promoted coding/entity label rows synced: `{synced_labels}`",
        "",
        "## Source Counts",
        "| source_type | records | mapped_candidates |",
        "| --- | ---: | ---: |",
    ]
    for source_type, count in source_counts.most_common():
        lines.append(f"| {source_type} | {count} | {mapped_counts.get(source_type, 0)} |")
    lines.extend(["", "## Raw Candidate Status"])
    for key, count in raw_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Duplicate Filters"])
    if duplicate_counts:
        for key, count in duplicate_counts.most_common():
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Production Interpretation",
            "- `mapped` rows remain public display locations for source records, not proof, habitats, or populations.",
            "- HauntedPlaces directory rows and non-strict OpenAlex/Crossref rows are excluded from this import.",
            "- Figure labels are normalized within this reviewed import batch to avoid display-card fragmentation from case/plural variants.",
            "- OpenLibrary and Wikidata rows are imported as records-only unless an independently reviewed display location exists later.",
            "- AYR map/index coordinates are normalized as source-visible public display locations with explicit non-verification notes.",
            "- Fisher's Ghost Internet Archive rows are retained as a micro-batch with duplicate/enrichment risk noted in the filter audit.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def import_reviewed_candidates(db_path: Path, frontend_path: Path, audit_csv: Path, report: Path) -> dict[str, int]:
    loaded, raw_counts = load_accepted_rows(CANDIDATE_FILES)
    with connect(db_path) as conn:
        ensure_schema(conn)
        existing_run_rows = load_existing_run_rows(conn, RUN_ID)
        if existing_run_rows:
            kept = existing_run_rows
            duplicate_counts = Counter({"existing_run_reused_for_idempotent_report": len(existing_run_rows)})
        else:
            kept, duplicate_counts = filter_new_rows(conn, loaded, frontend_path, RUN_ID)
        write_audit_csv(audit_csv, kept)
        for row in kept:
            insert_candidate(conn, row)
        promotion = promote_run(conn, RUN_ID)
        repaired_locations = repair_run_map_locations(conn, RUN_ID)
        synced_labels = sync_promoted_run_labels(conn, RUN_ID)
        conn.commit()
    write_report(report, loaded, kept, raw_counts, duplicate_counts, promotion, repaired_locations, synced_labels)
    return {"loaded": len(loaded), "kept": len(kept), **promotion}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--frontend-data", type=Path, default=DEFAULT_FRONTEND_DATA)
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    result = import_reviewed_candidates(args.db, args.frontend_data, args.audit_csv, args.report)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
