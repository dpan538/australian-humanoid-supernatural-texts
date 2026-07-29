#!/usr/bin/env python3
"""Import human-reviewed collection candidates into safe V2 staging."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import column_exists, normalize_space, now_iso, table_exists
from probe_public_sources import source_chain_id


EXPECTED_REVIEW_COLUMNS = [
    "candidate_id",
    "review_status",
    "accepted_record_type",
    "accepted_evidence_source_name",
    "accepted_evidence_source_url",
    "accepted_original_source_name",
    "accepted_publication_date",
    "evidence_strength",
    "source_stated_place_text",
    "location_role",
    "jurisdiction_state",
    "ethics_review_status",
    "display_decision",
    "reviewer_notes",
]


def load_review_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Review CSV is empty or missing a header")
        missing = [field for field in ("candidate_id", "review_status") if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"Review CSV missing required columns: {missing}")
        return [dict(row) for row in reader]


def validate_accept(row: dict[str, str], candidate: dict[str, Any] | None) -> tuple[bool, str]:
    if normalize_space(row.get("review_status")) != "accepted":
        return False, "not_accepted"
    evidence_mode = normalize_space(row.get("evidence_or_discovery") or (candidate or {}).get("evidence_or_discovery"))
    if evidence_mode == "discovery_only":
        if not normalize_space(row.get("accepted_evidence_source_name")) or not normalize_space(row.get("accepted_evidence_source_url")):
            return False, "discovery_only_without_accepted_evidence_source"
    ethics = normalize_space(row.get("ethics_review_status") or (candidate or {}).get("ethics_flags_json"))
    display = normalize_space(row.get("display_decision"))
    if any(token in ethics for token in ("sensitive", "restricted")) and display not in {"summary_only", "suppress_public"}:
        return False, "sensitive_or_restricted_without_safe_display_decision"
    if display in {"map", "public_map", "map_display"}:
        required = ["source_stated_place_text", "location_role", "jurisdiction_state"]
        missing = [field for field in required if not normalize_space(row.get(field))]
        if missing:
            return False, "map_promotion_missing_fields:" + ",".join(missing)
        return False, "map_promotion_requires_separate_geocode_review"
    return True, ""


def candidate_by_id(conn: sqlite3.Connection, candidate_id: str) -> dict[str, Any] | None:
    if not table_exists(conn, "collection_candidates"):
        return None
    row = conn.execute("SELECT * FROM collection_candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
    return dict(row) if row else None


def update_candidate_status(conn: sqlite3.Connection, candidate_id: str, status: str, notes: str) -> None:
    if not table_exists(conn, "collection_candidates"):
        return
    conn.execute(
        """
        UPDATE collection_candidates
        SET review_status = ?, reviewer_notes = ?, updated_at = ?
        WHERE candidate_id = ?
        """,
        (status, notes, now_iso(), candidate_id),
    )


def insert_source_chain(conn: sqlite3.Connection, row: dict[str, str], candidate: dict[str, Any] | None, run_id: str) -> None:
    if not table_exists(conn, "source_chains"):
        return
    ts = now_iso()
    candidate_id = row["candidate_id"]
    source_id = str((candidate or {}).get("source_id") or row.get("accepted_evidence_source_name") or "reviewed")
    evidence_name = row.get("accepted_evidence_source_name") or (candidate or {}).get("source_name") or ""
    evidence_url = row.get("accepted_evidence_source_url") or (candidate or {}).get("url") or ""
    original_name = row.get("accepted_original_source_name") or (candidate or {}).get("publication") or ""
    conn.execute(
        """
        INSERT INTO source_chains (
            source_chain_id, candidate_id, discovery_source_name, discovery_source_type,
            access_source_name, access_source_type, access_source_url,
            original_source_name, original_publication, original_publication_date,
            evidence_source_name, evidence_source_url, evidence_source_tier,
            evidence_strength, rights_status, metadata_only, full_text_available,
            source_chain_review_status, reviewer_notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_chain_id) DO UPDATE SET
            evidence_source_name=excluded.evidence_source_name,
            evidence_source_url=excluded.evidence_source_url,
            source_chain_review_status=excluded.source_chain_review_status,
            reviewer_notes=excluded.reviewer_notes,
            updated_at=excluded.updated_at
        """,
        (
            source_chain_id(candidate_id, source_id),
            candidate_id,
            (candidate or {}).get("source_name") or "",
            (candidate or {}).get("evidence_or_discovery") or "",
            (candidate or {}).get("source_name") or evidence_name,
            (candidate or {}).get("evidence_or_discovery") or "",
            (candidate or {}).get("url") or evidence_url,
            original_name,
            original_name,
            row.get("accepted_publication_date") or (candidate or {}).get("date_published") or "",
            evidence_name,
            evidence_url,
            (candidate or {}).get("source_tier") or "",
            row.get("evidence_strength") or "reviewed_metadata",
            (candidate or {}).get("rights_status") or "",
            1,
            0,
            "accepted",
            f"{run_id}: {row.get('reviewer_notes') or ''}".strip(),
            ts,
            ts,
        ),
    )


def compatible_v2_tables(conn: sqlite3.Connection) -> bool:
    required = {
        "source_items": ["title", "publication_or_organisation", "publication_date_text", "url", "source_tier", "created_at", "updated_at"],
        "narrative_units": ["migration_key", "working_title", "public_summary", "analysis_status", "display_mode", "created_at", "updated_at"],
        "narrative_source_links": ["narrative_id", "source_item_id", "relationship_type", "human_review_status", "created_at", "updated_at"],
    }
    for table, columns in required.items():
        if not table_exists(conn, table):
            return False
        if any(not column_exists(conn, table, column) for column in columns):
            return False
    return True


def migration_key(run_id: str, candidate_id: str) -> str:
    return "reviewed:" + hashlib.sha256(f"{run_id}|{candidate_id}".encode("utf-8")).hexdigest()[:24]


def insert_minimal_v2(conn: sqlite3.Connection, row: dict[str, str], candidate: dict[str, Any] | None, run_id: str) -> str:
    if not compatible_v2_tables(conn):
        return "manual_import_required_schema_mismatch"
    key = migration_key(run_id, row["candidate_id"])
    existing = conn.execute("SELECT narrative_id FROM narrative_units WHERE migration_key = ?", (key,)).fetchone()
    if existing:
        return "already_present"
    ts = now_iso()
    title = (candidate or {}).get("title") or row.get("accepted_evidence_source_name") or row["candidate_id"]
    source_name = row.get("accepted_original_source_name") or (candidate or {}).get("publication") or row.get("accepted_evidence_source_name") or ""
    source_url = row.get("accepted_evidence_source_url") or (candidate or {}).get("url") or ""
    source_tier = (candidate or {}).get("source_tier") or ""
    conn.execute(
        """
        INSERT INTO source_items (
            title, publication_or_organisation, publication_date_text, url, canonical_url,
            source_type, source_tier, source_mediation, publicness_status,
            rights_access_status, source_traceability_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            source_name,
            row.get("accepted_publication_date") or (candidate or {}).get("date_published") or "",
            source_url,
            source_url,
            row.get("accepted_record_type") or "reviewed_collection_candidate",
            source_tier,
            "reviewed_collection_expansion",
            "public_metadata",
            (candidate or {}).get("rights_status") or "metadata_only",
            "reviewed_source_chain",
            ts,
            ts,
        ),
    )
    source_item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    display_decision = normalize_space(row.get("display_decision")) or "metadata_only"
    display_mode = "summary_only" if display_decision == "summary_only" else "metadata_only"
    conn.execute(
        """
        INSERT INTO narrative_units (
            migration_key, working_title, public_summary, narrative_status,
            analysis_status, australia_relation, cultural_sensitivity,
            ethics_review_status, display_mode, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            key,
            title,
            (candidate or {}).get("snippet") or row.get("reviewer_notes") or "Reviewed collection expansion candidate.",
            "reviewed_candidate",
            "review_required",
            "australian_public_text",
            "needs_review",
            row.get("ethics_review_status") or "needs_review",
            display_mode,
            ts,
            ts,
        ),
    )
    narrative_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        """
        INSERT OR IGNORE INTO narrative_source_links (
            narrative_id, source_item_id, relationship_type, confidence,
            evidence_note, human_review_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            narrative_id,
            source_item_id,
            "original_publication",
            "needs_review",
            row.get("evidence_strength") or "",
            "accepted",
            ts,
            ts,
        ),
    )
    return "inserted_minimal_v2"


def import_reviewed(db_path: Path, review_csv: Path, run_id: str, execute: bool) -> dict[str, Any]:
    rows = load_review_rows(review_csv)
    accepted = 0
    rejected = 0
    skipped = 0
    inserted_v2 = 0
    notes: list[str] = []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if execute:
            missing = [table for table in ("collection_candidates", "source_chains") if not table_exists(conn, table)]
            if missing:
                raise RuntimeError("Missing migration tables: " + ", ".join(missing))
        for row in rows:
            candidate = candidate_by_id(conn, row.get("candidate_id", "")) if execute else None
            ok, reason = validate_accept(row, candidate)
            if not ok:
                if reason == "not_accepted":
                    skipped += 1
                else:
                    rejected += 1
                    notes.append(f"{row.get('candidate_id')}: {reason}")
                continue
            accepted += 1
            if execute:
                update_candidate_status(conn, row["candidate_id"], "accepted", row.get("reviewer_notes") or "")
                insert_source_chain(conn, row, candidate, run_id)
                result = insert_minimal_v2(conn, row, candidate, run_id)
                if result == "inserted_minimal_v2":
                    inserted_v2 += 1
                elif result != "already_present":
                    notes.append(f"{row.get('candidate_id')}: {result}")
        if execute:
            conn.commit()

    report_path = ROOT / "data" / "processed" / "v2" / f"{run_id}_reviewed_import_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Reviewed Candidate Import Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Review CSV: `{review_csv}`",
        f"- Mode: `{'execute' if execute else 'dry_run'}`",
        f"- Accepted rows eligible: `{accepted}`",
        f"- Rejected accepted rows: `{rejected}`",
        f"- Skipped non-accepted rows: `{skipped}`",
        f"- Minimal V2 inserts: `{inserted_v2}`",
    ]
    if notes:
        lines.extend(["", "## Notes"])
        lines.extend([f"- {note}" for note in notes[:50]])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"accepted": accepted, "rejected": rejected, "skipped": skipped, "inserted_v2": inserted_v2, "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--review-csv", required=True, help="human-reviewed CSV path")
    parser.add_argument("--run-id", required=True, help="import run id")
    parser.add_argument("--dry-run", action="store_true", help="validate without writing")
    parser.add_argument("--execute", action="store_true", help="write accepted staging/source-chain rows")
    args = parser.parse_args()

    execute = bool(args.execute and not args.dry_run)
    summary = import_reviewed(Path(args.db), Path(args.review_csv), args.run_id, execute=execute)
    print(f"Reviewed import {'executed' if execute else 'dry run'}: {summary['accepted']} eligible accepted rows.")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
