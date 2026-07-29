#!/usr/bin/env python3
"""Create no-credential structured endpoint harvest tables."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import index_exists, now_iso, table_exists
from migrate_autoharvest_gap_v2 import migrate as migrate_gap


TABLE_SQL = {
    "noauth_endpoint_inventory": """
        CREATE TABLE IF NOT EXISTS noauth_endpoint_inventory (
            endpoint_id TEXT PRIMARY KEY,
            route_id TEXT,
            source_id TEXT,
            source_name TEXT,
            source_tier TEXT,
            route_family TEXT,
            state TEXT,
            domain TEXT,
            base_url TEXT,
            endpoint_url TEXT NOT NULL,
            endpoint_type TEXT,
            noauth_verified INTEGER DEFAULT 0,
            robots_allowed INTEGER DEFAULT 0,
            login_required INTEGER DEFAULT 0,
            api_key_required INTEGER DEFAULT 0,
            paywall_required INTEGER DEFAULT 0,
            terms_status TEXT,
            confidence REAL DEFAULT 0,
            status TEXT DEFAULT 'discovered',
            discovered_at TEXT NOT NULL,
            last_tested_at TEXT,
            notes TEXT
        )
    """,
    "noauth_endpoint_queries": """
        CREATE TABLE IF NOT EXISTS noauth_endpoint_queries (
            endpoint_query_id TEXT PRIMARY KEY,
            endpoint_id TEXT,
            run_id TEXT,
            query_text TEXT,
            controlled_term TEXT,
            date_term TEXT,
            locality TEXT,
            target_state TEXT,
            query_url TEXT,
            status TEXT DEFAULT 'queued',
            priority_score REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            attempted_at TEXT,
            notes TEXT
        )
    """,
    "noauth_endpoint_records": """
        CREATE TABLE IF NOT EXISTS noauth_endpoint_records (
            endpoint_record_id TEXT PRIMARY KEY,
            run_id TEXT,
            endpoint_id TEXT,
            endpoint_query_id TEXT,
            route_id TEXT,
            source_name TEXT,
            source_tier TEXT,
            endpoint_type TEXT,
            item_url TEXT,
            item_id TEXT,
            title TEXT,
            description TEXT,
            creator TEXT,
            publisher TEXT,
            date_text TEXT,
            inferred_year INTEGER,
            coverage_start_year INTEGER,
            coverage_end_year INTEGER,
            subject_terms TEXT,
            place_text TEXT,
            format_text TEXT,
            rights_text TEXT,
            metadata_json TEXT,
            controlled_term_hits TEXT,
            temporal_evidence_json TEXT,
            item_level_confidence REAL DEFAULT 0,
            target_gap_score REAL DEFAULT 0,
            target_gap_eligible INTEGER DEFAULT 0,
            gate_reasons_json TEXT,
            duplicate_key TEXT,
            duplicate_status TEXT DEFAULT 'unchecked',
            created_at TEXT NOT NULL
        )
    """,
    "noauth_endpoint_route_stats": """
        CREATE TABLE IF NOT EXISTS noauth_endpoint_route_stats (
            run_id TEXT,
            endpoint_id TEXT,
            endpoint_type TEXT,
            source_name TEXT,
            queries_attempted INTEGER DEFAULT 0,
            records_seen INTEGER DEFAULT 0,
            target_gap_records INTEGER DEFAULT 0,
            near_misses INTEGER DEFAULT 0,
            duplicates INTEGER DEFAULT 0,
            noise INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            yield_score REAL DEFAULT 0,
            recommended_action TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_id, endpoint_id)
        )
    """,
}

INDEX_SQL = {
    "idx_noauth_endpoint_inventory_type": "CREATE INDEX IF NOT EXISTS idx_noauth_endpoint_inventory_type ON noauth_endpoint_inventory(endpoint_type)",
    "idx_noauth_endpoint_inventory_status": "CREATE INDEX IF NOT EXISTS idx_noauth_endpoint_inventory_status ON noauth_endpoint_inventory(status)",
    "idx_noauth_endpoint_queries_status_priority": "CREATE INDEX IF NOT EXISTS idx_noauth_endpoint_queries_status_priority ON noauth_endpoint_queries(status, priority_score)",
    "idx_noauth_endpoint_records_run": "CREATE INDEX IF NOT EXISTS idx_noauth_endpoint_records_run ON noauth_endpoint_records(run_id)",
    "idx_noauth_endpoint_records_target": "CREATE INDEX IF NOT EXISTS idx_noauth_endpoint_records_target ON noauth_endpoint_records(target_gap_eligible)",
    "idx_noauth_endpoint_records_duplicate": "CREATE INDEX IF NOT EXISTS idx_noauth_endpoint_records_duplicate ON noauth_endpoint_records(duplicate_key)",
}


def migrate(db_path: Path) -> dict[str, object]:
    migrate_gap(db_path)
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
