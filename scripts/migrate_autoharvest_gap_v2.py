#!/usr/bin/env python3
"""Add gap-targeted autoharvest temporal evidence schema."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import column_exists, index_exists, now_iso, table_exists
from migrate_autoharvest_v1 import migrate as migrate_v1


PROVISIONAL_COLUMNS = {
    "harvest_mode": "TEXT",
    "route_id": "TEXT",
    "target_gap_eligible": "INTEGER DEFAULT 0",
    "target_gap_reason": "TEXT",
    "temporal_evidence_type": "TEXT",
    "source_publication_year": "INTEGER",
    "narrative_year": "INTEGER",
    "coverage_start_year": "INTEGER",
    "coverage_end_year": "INTEGER",
    "date_confidence": "REAL DEFAULT 0",
    "term_hit_confidence": "REAL DEFAULT 0",
    "item_level_confidence": "REAL DEFAULT 0",
    "auxiliary_status": "TEXT",
    "target_effective_weight": "REAL DEFAULT 0",
    "item_format": "TEXT",
    "item_format_confidence": "REAL DEFAULT 0",
    "record_publication_year": "INTEGER",
    "record_publication_date_text": "TEXT",
    "narrative_date_text": "TEXT",
    "collection_coverage_date_text": "TEXT",
    "target_date_basis": "TEXT",
}

CANDIDATE_COLUMNS = {
    "temporal_evidence_type": "TEXT",
    "source_publication_year": "INTEGER",
    "narrative_year": "INTEGER",
    "coverage_start_year": "INTEGER",
    "coverage_end_year": "INTEGER",
    "date_confidence": "REAL DEFAULT 0",
    "term_hit_confidence": "REAL DEFAULT 0",
    "item_level_confidence": "REAL DEFAULT 0",
    "target_gap_candidate": "INTEGER DEFAULT 0",
    "item_format": "TEXT",
    "item_format_confidence": "REAL DEFAULT 0",
    "record_publication_year": "INTEGER",
    "record_publication_date_text": "TEXT",
    "narrative_date_text": "TEXT",
    "collection_coverage_date_text": "TEXT",
    "target_date_basis": "TEXT",
}

TEMPORAL_EVIDENCE_SQL = """
CREATE TABLE IF NOT EXISTS harvest_temporal_evidence (
    temporal_evidence_id TEXT PRIMARY KEY,
    run_id TEXT,
    candidate_id TEXT,
    provisional_record_id TEXT,
    evidence_type TEXT,
    evidence_text TEXT,
    extracted_year INTEGER,
    coverage_start_year INTEGER,
    coverage_end_year INTEGER,
    term_nearby TEXT,
    locality_nearby TEXT,
    source_url TEXT,
    confidence REAL,
    created_at TEXT NOT NULL
)
"""

INDEX_SQL = {
    "idx_provisional_records_target_gap_eligible": "CREATE INDEX IF NOT EXISTS idx_provisional_records_target_gap_eligible ON provisional_records(target_gap_eligible)",
    "idx_provisional_records_source_publication_year": "CREATE INDEX IF NOT EXISTS idx_provisional_records_source_publication_year ON provisional_records(source_publication_year)",
    "idx_provisional_records_narrative_year": "CREATE INDEX IF NOT EXISTS idx_provisional_records_narrative_year ON provisional_records(narrative_year)",
    "idx_harvest_candidates_target_gap_candidate": "CREATE INDEX IF NOT EXISTS idx_harvest_candidates_target_gap_candidate ON harvest_candidates(target_gap_candidate)",
    "idx_harvest_temporal_evidence_run_id": "CREATE INDEX IF NOT EXISTS idx_harvest_temporal_evidence_run_id ON harvest_temporal_evidence(run_id)",
    "idx_harvest_temporal_evidence_candidate_id": "CREATE INDEX IF NOT EXISTS idx_harvest_temporal_evidence_candidate_id ON harvest_temporal_evidence(candidate_id)",
}


def add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> list[str]:
    added: list[str] = []
    for name, definition in columns.items():
        if not column_exists(conn, table, name):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
            added.append(f"{table}.{name}")
    return added


def migrate(db_path: Path) -> dict[str, object]:
    migrate_v1(db_path)
    added_columns: list[str] = []
    created_tables: list[str] = []
    created_indexes: list[str] = []
    with sqlite3.connect(db_path) as conn:
        if table_exists(conn, "provisional_records"):
            added_columns.extend(add_columns(conn, "provisional_records", PROVISIONAL_COLUMNS))
        if table_exists(conn, "harvest_candidates"):
            added_columns.extend(add_columns(conn, "harvest_candidates", CANDIDATE_COLUMNS))
        was_present = table_exists(conn, "harvest_temporal_evidence")
        conn.execute(TEMPORAL_EVIDENCE_SQL)
        if not was_present:
            created_tables.append("harvest_temporal_evidence")
        for name, sql in INDEX_SQL.items():
            existed = index_exists(conn, name)
            conn.execute(sql)
            if not existed:
                created_indexes.append(name)
        conn.commit()
    return {
        "generated": now_iso(),
        "added_columns": added_columns,
        "created_tables": created_tables,
        "created_indexes": created_indexes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    print(migrate(Path(args.db)))


if __name__ == "__main__":
    main()
