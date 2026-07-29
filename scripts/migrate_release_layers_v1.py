#!/usr/bin/env python3
"""Create final internal release layer tables."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import column_exists, index_exists, now_iso, table_exists
from migrate_research_volume_expansion_v1 import migrate as migrate_volume


TABLE_SQL = {
    "release_metadata_gap_items": """
        CREATE TABLE IF NOT EXISTS release_metadata_gap_items (
            release_item_id TEXT PRIMARY KEY,
            source_lead_id TEXT,
            source_table TEXT,
            source_row_id TEXT,
            release_layer TEXT DEFAULT 'metadata_only_gap',
            title TEXT,
            description TEXT,
            url TEXT,
            source_name TEXT,
            source_tier TEXT,
            source_family TEXT,
            route_family TEXT,
            inferred_year INTEGER,
            coverage_start_year INTEGER,
            coverage_end_year INTEGER,
            target_state TEXT,
            target_locality TEXT,
            temporal_signal TEXT,
            term_signal TEXT,
            place_signal TEXT,
            evidence_gap TEXT,
            display_label TEXT DEFAULT 'Metadata-only lead',
            public_record_status TEXT DEFAULT 'not_public_record',
            map_display_status TEXT DEFAULT 'not_public_map',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "release_lead_overlay_items": """
        CREATE TABLE IF NOT EXISTS release_lead_overlay_items (
            release_lead_id TEXT PRIMARY KEY,
            source_lead_id TEXT,
            source_table TEXT,
            source_row_id TEXT,
            title TEXT,
            url TEXT,
            source_name TEXT,
            source_family TEXT,
            route_family TEXT,
            inferred_year INTEGER,
            coverage_start_year INTEGER,
            coverage_end_year INTEGER,
            target_state TEXT,
            target_locality TEXT,
            lead_score REAL,
            priority_bucket TEXT,
            evidence_gap TEXT,
            blocker TEXT,
            display_label TEXT DEFAULT 'Research lead',
            public_record_status TEXT DEFAULT 'not_public_record',
            map_display_status TEXT DEFAULT 'not_public_map',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "release_source_intelligence_items": """
        CREATE TABLE IF NOT EXISTS release_source_intelligence_items (
            source_intel_id TEXT PRIMARY KEY,
            source_table TEXT,
            source_row_id TEXT,
            source_name TEXT,
            source_family TEXT,
            route_family TEXT,
            state TEXT,
            blocker TEXT,
            opportunity_type TEXT,
            count_weight REAL DEFAULT 1.0,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
}

INDEX_SQL = {
    "idx_release_metadata_gap_year": "CREATE INDEX IF NOT EXISTS idx_release_metadata_gap_year ON release_metadata_gap_items(inferred_year)",
    "idx_release_metadata_gap_state": "CREATE INDEX IF NOT EXISTS idx_release_metadata_gap_state ON release_metadata_gap_items(target_state)",
    "idx_release_lead_overlay_year": "CREATE INDEX IF NOT EXISTS idx_release_lead_overlay_year ON release_lead_overlay_items(inferred_year)",
    "idx_release_lead_overlay_state": "CREATE INDEX IF NOT EXISTS idx_release_lead_overlay_state ON release_lead_overlay_items(target_state)",
}


def expected_columns(sql: str) -> list[tuple[str, str]]:
    conn = sqlite3.connect(":memory:")
    conn.execute(sql)
    table_name = sql.split("CREATE TABLE IF NOT EXISTS", 1)[1].split("(", 1)[0].strip()
    rows = [(row[1], row[2] or "TEXT") for row in conn.execute(f"PRAGMA table_info({table_name})")]
    conn.close()
    return rows


def migrate(db_path: Path) -> dict[str, object]:
    migrate_volume(db_path)
    created_tables: list[str] = []
    added_columns: list[str] = []
    created_indexes: list[str] = []
    with sqlite3.connect(db_path) as conn:
        for table, sql in TABLE_SQL.items():
            existed = table_exists(conn, table)
            conn.execute(sql)
            if not existed:
                created_tables.append(table)
            for column, column_type in expected_columns(sql):
                if not column_exists(conn, table, column):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                    added_columns.append(f"{table}.{column}")
        for name, sql in INDEX_SQL.items():
            existed = index_exists(conn, name)
            conn.execute(sql)
            if not existed:
                created_indexes.append(name)
        conn.commit()
    return {"generated": now_iso(), "created_tables": created_tables, "added_columns": added_columns, "created_indexes": created_indexes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    print(migrate(Path(args.db)))


if __name__ == "__main__":
    main()
