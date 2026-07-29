#!/usr/bin/env python3
"""Create target-gap lead-mode tables."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import index_exists, now_iso, table_exists
from migrate_structured_near_miss_v1 import migrate as migrate_structured_near


TABLE_SQL = {
    "target_gap_leads": """
        CREATE TABLE IF NOT EXISTS target_gap_leads (
            lead_id TEXT PRIMARY KEY,
            source_run_id TEXT,
            source_table TEXT,
            source_row_id TEXT,
            lead_type TEXT NOT NULL,
            lead_status TEXT DEFAULT 'open',
            lead_score REAL DEFAULT 0,
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
    "target_gap_lead_clusters": """
        CREATE TABLE IF NOT EXISTS target_gap_lead_clusters (
            cluster_id TEXT PRIMARY KEY,
            cluster_type TEXT,
            cluster_label TEXT,
            lead_count INTEGER DEFAULT 0,
            max_lead_score REAL DEFAULT 0,
            representative_lead_id TEXT,
            recommended_action TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "constraint_relaxation_scenarios": """
        CREATE TABLE IF NOT EXISTS constraint_relaxation_scenarios (
            scenario_id TEXT PRIMARY KEY,
            scenario_name TEXT,
            constraint_changed TEXT,
            expected_new_records INTEGER DEFAULT 0,
            expected_new_leads INTEGER DEFAULT 0,
            quality_risk TEXT,
            source_chain_risk TEXT,
            ethics_risk TEXT,
            implementation_cost TEXT,
            owner_effort TEXT,
            recommendation TEXT,
            created_at TEXT NOT NULL
        )
    """,
}

INDEX_SQL = {
    "idx_target_gap_leads_type": "CREATE INDEX IF NOT EXISTS idx_target_gap_leads_type ON target_gap_leads(lead_type)",
    "idx_target_gap_leads_priority": "CREATE INDEX IF NOT EXISTS idx_target_gap_leads_priority ON target_gap_leads(priority_bucket)",
    "idx_target_gap_leads_score": "CREATE INDEX IF NOT EXISTS idx_target_gap_leads_score ON target_gap_leads(lead_score)",
    "idx_target_gap_leads_blocker": "CREATE INDEX IF NOT EXISTS idx_target_gap_leads_blocker ON target_gap_leads(constraint_blocker)",
    "idx_target_gap_leads_state": "CREATE INDEX IF NOT EXISTS idx_target_gap_leads_state ON target_gap_leads(target_state)",
    "idx_target_gap_leads_year": "CREATE INDEX IF NOT EXISTS idx_target_gap_leads_year ON target_gap_leads(inferred_year)",
    "idx_target_gap_leads_duplicate": "CREATE INDEX IF NOT EXISTS idx_target_gap_leads_duplicate ON target_gap_leads(duplicate_key)",
}


def migrate(db_path: Path) -> dict[str, object]:
    migrate_structured_near(db_path)
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
