#!/usr/bin/env python3
"""Create structured endpoint near-miss recovery tables."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import index_exists, now_iso, table_exists
from migrate_structured_endpoint_harvest_v1 import migrate as migrate_structured


TABLE_SQL = {
    "structured_endpoint_near_misses": """
        CREATE TABLE IF NOT EXISTS structured_endpoint_near_misses (
            near_miss_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            endpoint_record_id TEXT,
            endpoint_id TEXT,
            endpoint_query_id TEXT,
            source_name TEXT,
            source_tier TEXT,
            endpoint_type TEXT,
            route_family TEXT,
            item_url TEXT,
            item_id TEXT,
            title TEXT,
            description TEXT,
            date_text TEXT,
            inferred_year INTEGER,
            coverage_start_year INTEGER,
            coverage_end_year INTEGER,
            place_text TEXT,
            controlled_term_hits TEXT,
            temporal_evidence_json TEXT,
            gate_reasons_json TEXT,
            near_miss_type TEXT,
            recoverability_score REAL DEFAULT 0,
            recovery_action TEXT,
            recovery_status TEXT DEFAULT 'queued',
            detail_url TEXT,
            enrichment_attempted INTEGER DEFAULT 0,
            enriched_record_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "structured_endpoint_enriched_records": """
        CREATE TABLE IF NOT EXISTS structured_endpoint_enriched_records (
            enriched_record_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            near_miss_id TEXT,
            endpoint_record_id TEXT,
            source_name TEXT,
            source_tier TEXT,
            endpoint_type TEXT,
            detail_url TEXT,
            item_url TEXT,
            title TEXT,
            description TEXT,
            date_text TEXT,
            inferred_year INTEGER,
            coverage_start_year INTEGER,
            coverage_end_year INTEGER,
            place_text TEXT,
            controlled_term_hits TEXT,
            temporal_evidence_json TEXT,
            item_level_confidence REAL DEFAULT 0,
            target_gap_score REAL DEFAULT 0,
            target_gap_eligible INTEGER DEFAULT 0,
            gate_reasons_json TEXT,
            evidence_source_name TEXT,
            evidence_source_url TEXT,
            access_source_name TEXT,
            access_source_url TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL
        )
    """,
}

INDEX_SQL = {
    "idx_structured_near_misses_run_id": "CREATE INDEX IF NOT EXISTS idx_structured_near_misses_run_id ON structured_endpoint_near_misses(run_id)",
    "idx_structured_near_misses_type": "CREATE INDEX IF NOT EXISTS idx_structured_near_misses_type ON structured_endpoint_near_misses(near_miss_type)",
    "idx_structured_near_misses_status": "CREATE INDEX IF NOT EXISTS idx_structured_near_misses_status ON structured_endpoint_near_misses(recovery_status)",
    "idx_structured_enriched_run_id": "CREATE INDEX IF NOT EXISTS idx_structured_enriched_run_id ON structured_endpoint_enriched_records(run_id)",
    "idx_structured_enriched_target": "CREATE INDEX IF NOT EXISTS idx_structured_enriched_target ON structured_endpoint_enriched_records(target_gap_eligible)",
}


def migrate(db_path: Path) -> dict[str, object]:
    migrate_structured(db_path)
    created_tables: list[str] = []
    created_indexes: list[str] = []
    with sqlite3.connect(db_path) as conn:
        for name, sql in TABLE_SQL.items():
            existed = table_exists(conn, name)
            conn.execute(sql)
            if not existed:
                created_tables.append(name)
        for name, sql in INDEX_SQL.items():
            existed = index_exists(conn, name)
            conn.execute(sql)
            if not existed:
                created_indexes.append(name)
        conn.commit()
    return {"generated": now_iso(), "created_tables": created_tables, "created_indexes": created_indexes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    print(migrate(Path(args.db)))


if __name__ == "__main__":
    main()
