#!/usr/bin/env python3
"""Create research-volume expansion tables."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import column_exists, index_exists, now_iso, table_exists
from migrate_autoharvest_gap_v2 import migrate as migrate_gap
from migrate_target_gap_leads_v1 import migrate as migrate_leads


TABLE_SQL = {
    "auxiliary_source_intelligence": """
        CREATE TABLE IF NOT EXISTS auxiliary_source_intelligence (
            intelligence_id TEXT PRIMARY KEY,
            run_id TEXT,
            source_table TEXT,
            source_row_id TEXT,
            intelligence_type TEXT NOT NULL,
            intelligence_status TEXT DEFAULT 'open',
            intelligence_score REAL DEFAULT 0,
            priority_bucket TEXT,
            title TEXT,
            description TEXT,
            url TEXT,
            source_name TEXT,
            source_tier TEXT,
            source_family TEXT,
            route_family TEXT,
            target_state TEXT,
            target_locality TEXT,
            inferred_year INTEGER,
            coverage_start_year INTEGER,
            coverage_end_year INTEGER,
            time_band TEXT,
            temporal_signal TEXT,
            term_signal TEXT,
            place_signal TEXT,
            evidence_gap TEXT,
            constraint_blocker TEXT,
            recommended_next_action TEXT,
            source_chain_json TEXT,
            robots_status TEXT,
            rights_status TEXT,
            ethics_status TEXT,
            duplicate_key TEXT,
            duplicate_status TEXT DEFAULT 'unchecked',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "research_volume_runs": """
        CREATE TABLE IF NOT EXISTS research_volume_runs (
            run_id TEXT PRIMARY KEY,
            status TEXT,
            target_new_items INTEGER DEFAULT 0,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            new_items INTEGER DEFAULT 0,
            provisional_records INTEGER DEFAULT 0,
            target_gap_leads INTEGER DEFAULT 0,
            metadata_only_leads INTEGER DEFAULT 0,
            auxiliary_source_intelligence INTEGER DEFAULT 0,
            priority_items INTEGER DEFAULT 0,
            target_period_items INTEGER DEFAULT 0,
            non_aggregator_items INTEGER DEFAULT 0,
            public_records_mutated INTEGER DEFAULT 0,
            map_flags_mutated INTEGER DEFAULT 0,
            frontend_artifacts_mutated INTEGER DEFAULT 0,
            notes TEXT
        )
    """,
    "research_volume_items": """
        CREATE TABLE IF NOT EXISTS research_volume_items (
            item_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            layer TEXT NOT NULL,
            linked_table TEXT,
            linked_row_id TEXT,
            source_name TEXT,
            source_tier TEXT,
            source_family TEXT,
            route_family TEXT,
            target_state TEXT,
            target_locality TEXT,
            inferred_year INTEGER,
            time_band TEXT,
            temporal_signal TEXT,
            term_signal TEXT,
            priority_score REAL DEFAULT 0,
            priority_bucket TEXT,
            evidence_gap TEXT,
            constraint_blocker TEXT,
            is_priority_item INTEGER DEFAULT 0,
            is_target_period INTEGER DEFAULT 0,
            is_non_aggregator INTEGER DEFAULT 0,
            duplicate_key TEXT,
            duplicate_status TEXT DEFAULT 'unchecked',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "research_volume_milestones": """
        CREATE TABLE IF NOT EXISTS research_volume_milestones (
            run_id TEXT,
            milestone_value INTEGER,
            reached_at TEXT,
            report_path TEXT,
            total_new_items INTEGER DEFAULT 0,
            provisional_records INTEGER DEFAULT 0,
            target_gap_leads INTEGER DEFAULT 0,
            metadata_only_leads INTEGER DEFAULT 0,
            auxiliary_source_intelligence INTEGER DEFAULT 0,
            priority_items INTEGER DEFAULT 0,
            target_period_items INTEGER DEFAULT 0,
            non_aggregator_items INTEGER DEFAULT 0,
            duplicate_noise_rate REAL DEFAULT 0,
            public_records_mutated INTEGER DEFAULT 0,
            map_flags_mutated INTEGER DEFAULT 0,
            frontend_artifacts_mutated INTEGER DEFAULT 0,
            audit_status TEXT,
            notes TEXT,
            PRIMARY KEY (run_id, milestone_value)
        )
    """,
}

INDEX_SQL = {
    "idx_aux_source_intelligence_run": "CREATE INDEX IF NOT EXISTS idx_aux_source_intelligence_run ON auxiliary_source_intelligence(run_id)",
    "idx_aux_source_intelligence_type": "CREATE INDEX IF NOT EXISTS idx_aux_source_intelligence_type ON auxiliary_source_intelligence(intelligence_type)",
    "idx_aux_source_intelligence_blocker": "CREATE INDEX IF NOT EXISTS idx_aux_source_intelligence_blocker ON auxiliary_source_intelligence(constraint_blocker)",
    "idx_research_volume_items_run": "CREATE INDEX IF NOT EXISTS idx_research_volume_items_run ON research_volume_items(run_id)",
    "idx_research_volume_items_layer": "CREATE INDEX IF NOT EXISTS idx_research_volume_items_layer ON research_volume_items(layer)",
    "idx_research_volume_items_priority": "CREATE INDEX IF NOT EXISTS idx_research_volume_items_priority ON research_volume_items(is_priority_item)",
    "idx_research_volume_items_period": "CREATE INDEX IF NOT EXISTS idx_research_volume_items_period ON research_volume_items(is_target_period)",
    "idx_research_volume_items_state": "CREATE INDEX IF NOT EXISTS idx_research_volume_items_state ON research_volume_items(target_state)",
}


def expected_columns(sql: str) -> list[tuple[str, str]]:
    conn = sqlite3.connect(":memory:")
    conn.execute(sql)
    table_name = sql.split("CREATE TABLE IF NOT EXISTS", 1)[1].split("(", 1)[0].strip()
    rows = [(row[1], row[2] or "TEXT") for row in conn.execute(f"PRAGMA table_info({table_name})")]
    conn.close()
    return rows


def migrate(db_path: Path) -> dict[str, object]:
    migrate_gap(db_path)
    migrate_leads(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
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
