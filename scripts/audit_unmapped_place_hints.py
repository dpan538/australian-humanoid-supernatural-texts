#!/usr/bin/env python3
"""Find unmapped records and candidates with place hints for human review."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import normalize_space, now_iso, stable_review_id, table_exists, write_csv


OUTPUT_FIELDS = [
    "geocode_review_id",
    "candidate_id",
    "record_id",
    "narrative_unit_id",
    "source_stated_place_text",
    "jurisdiction_state",
    "location_role",
    "geocode_confidence",
    "display_allowed",
    "review_status",
    "reviewer_notes",
]


def locality_terms(matrix_path: Path) -> dict[str, list[str]]:
    matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8")) or {}
    result: dict[str, list[str]] = {}
    for state, config in (matrix.get("states") or {}).items():
        result[state] = list(config.get("locality_terms") or [])
    return result


def mapped_record_ids(conn: sqlite3.Connection) -> set[str]:
    mapped: set[str] = set()
    if table_exists(conn, "record_locations"):
        for row in conn.execute("SELECT DISTINCT record_id FROM record_locations WHERE record_id IS NOT NULL").fetchall():
            mapped.add(str(row["record_id"]))
    if table_exists(conn, "legacy_record_mappings") and table_exists(conn, "narrative_locations"):
        for row in conn.execute(
            """
            SELECT DISTINCT m.legacy_record_id
            FROM legacy_record_mappings m
            JOIN narrative_locations nl ON nl.narrative_id = m.narrative_id
            WHERE m.legacy_record_id IS NOT NULL
            """
        ).fetchall():
            mapped.add(str(row["legacy_record_id"]))
    return mapped


def find_place(text: str, terms_by_state: dict[str, list[str]]) -> tuple[str, str]:
    clean = normalize_space(text)
    for state, terms in terms_by_state.items():
        for term in terms:
            if normalize_space(term) and normalize_space(term) in clean:
                return term, state
    return "", ""


def row_for_review(
    *,
    candidate_id: str = "",
    record_id: str = "",
    narrative_unit_id: str = "",
    place: str,
    state: str,
    location_role: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "geocode_review_id": stable_review_id(candidate_id, record_id, narrative_unit_id, place, state),
        "candidate_id": candidate_id,
        "record_id": record_id,
        "narrative_unit_id": narrative_unit_id,
        "source_stated_place_text": place,
        "jurisdiction_state": state,
        "location_role": location_role,
        "geocode_confidence": "needs_review",
        "display_allowed": 0,
        "review_status": "needs_review",
        "reviewer_notes": notes,
    }


def insert_review_row(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO geocode_review_queue (
            geocode_review_id, record_id, narrative_unit_id, candidate_id,
            source_stated_place_text, jurisdiction_state, location_role,
            geocode_confidence, display_allowed, review_status,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(geocode_review_id) DO UPDATE SET
            source_stated_place_text=excluded.source_stated_place_text,
            jurisdiction_state=excluded.jurisdiction_state,
            location_role=excluded.location_role,
            geocode_confidence=excluded.geocode_confidence,
            display_allowed=excluded.display_allowed,
            review_status=excluded.review_status,
            updated_at=excluded.updated_at
        """,
        (
            row["geocode_review_id"],
            row["record_id"],
            row["narrative_unit_id"],
            row["candidate_id"],
            row["source_stated_place_text"],
            row["jurisdiction_state"],
            row["location_role"],
            row["geocode_confidence"],
            row["display_allowed"],
            row["review_status"],
            ts,
            ts,
        ),
    )


def audit(db_path: Path, out_path: Path, matrix_path: Path = ROOT / "config" / "query_matrix_1926_1976.yml") -> list[dict[str, Any]]:
    terms = locality_terms(matrix_path)
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "geocode_review_queue"):
            raise RuntimeError("Missing geocode_review_queue. Run collection expansion migration first.")
        mapped = mapped_record_ids(conn)

        if table_exists(conn, "collection_candidates"):
            for candidate in conn.execute(
                """
                SELECT candidate_id, source_stated_place_text, inferred_state, location_role,
                       mappability_hint, target_locality, target_state
                FROM collection_candidates
                WHERE COALESCE(review_status, '') != 'rejected'
                """
            ).fetchall():
                place = candidate["source_stated_place_text"] or ""
                state = candidate["inferred_state"] or candidate["target_state"] or ""
                if not place and candidate["mappability_hint"] == "high":
                    place = candidate["target_locality"] or ""
                if place:
                    rows.append(
                        row_for_review(
                            candidate_id=str(candidate["candidate_id"]),
                            place=place,
                            state=state,
                            location_role=candidate["location_role"] or "",
                            notes="candidate place hint requires human geocode review",
                        )
                    )

        if table_exists(conn, "records"):
            for record in conn.execute(
                """
                SELECT record_id, title, snippet, full_text_path
                FROM records
                WHERE record_id IS NOT NULL
                """
            ).fetchall():
                record_id = str(record["record_id"])
                if record_id in mapped:
                    continue
                text = " ".join(str(record[key] or "") for key in ("title", "snippet", "full_text_path"))
                place, state = find_place(text, terms)
                if place:
                    rows.append(
                        row_for_review(
                            record_id=record_id,
                            place=place,
                            state=state,
                            notes="legacy record has locality-like text but no reviewed map flag",
                        )
                    )

        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for row in rows:
            if row["geocode_review_id"] in seen:
                continue
            seen.add(row["geocode_review_id"])
            insert_review_row(conn, row)
            deduped.append(row)
        conn.commit()

    write_csv(out_path, deduped, OUTPUT_FIELDS)
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--out", required=True, help="review CSV output path")
    parser.add_argument("--matrix", default=str(ROOT / "config" / "query_matrix_1926_1976.yml"), help="query matrix YAML for locality terms")
    args = parser.parse_args()

    rows = audit(Path(args.db), Path(args.out), Path(args.matrix))
    print(f"Wrote {len(rows)} unmapped place-hint review rows: {args.out}")


if __name__ == "__main__":
    main()
