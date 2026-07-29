#!/usr/bin/env python3
"""Add the no-auth autoharvest provisional growth schema."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import column_exists, index_exists, now_iso, table_exists


TABLE_SQL = {
    "harvest_runs": """
        CREATE TABLE IF NOT EXISTS harvest_runs (
            run_id TEXT PRIMARY KEY,
            run_name TEXT,
            status TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            target_effective_records INTEGER,
            effective_records_added INTEGER DEFAULT 0,
            candidates_seen INTEGER DEFAULT 0,
            pages_fetched INTEGER DEFAULT 0,
            routes_attempted INTEGER DEFAULT 0,
            last_checkpoint_path TEXT,
            stop_reason TEXT,
            notes TEXT
        )
    """,
    "harvest_frontier": """
        CREATE TABLE IF NOT EXISTS harvest_frontier (
            frontier_id TEXT PRIMARY KEY,
            run_id TEXT,
            route_id TEXT,
            source_id TEXT,
            source_name TEXT,
            source_tier TEXT,
            route_family TEXT,
            state TEXT,
            url TEXT NOT NULL,
            url_type TEXT,
            parent_url TEXT,
            depth INTEGER DEFAULT 0,
            priority_score REAL DEFAULT 0,
            status TEXT DEFAULT 'queued',
            retry_count INTEGER DEFAULT 0,
            next_attempt_at TEXT,
            robots_status TEXT,
            last_http_status INTEGER,
            discovered_at TEXT NOT NULL,
            last_attempted_at TEXT,
            notes TEXT
        )
    """,
    "harvest_pages": """
        CREATE TABLE IF NOT EXISTS harvest_pages (
            page_id TEXT PRIMARY KEY,
            run_id TEXT,
            frontier_id TEXT,
            route_id TEXT,
            url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            http_status INTEGER,
            content_type TEXT,
            content_length INTEGER,
            title TEXT,
            canonical_url TEXT,
            text_sample TEXT,
            link_count INTEGER DEFAULT 0,
            pdf_link_count INTEGER DEFAULT 0,
            relevance_score REAL DEFAULT 0,
            stored_body_path TEXT,
            metadata_json TEXT,
            robots_allowed INTEGER,
            fetch_status TEXT,
            error TEXT
        )
    """,
    "harvest_candidates": """
        CREATE TABLE IF NOT EXISTS harvest_candidates (
            candidate_id TEXT PRIMARY KEY,
            run_id TEXT,
            page_id TEXT,
            route_id TEXT,
            source_id TEXT,
            source_name TEXT,
            source_tier TEXT,
            route_family TEXT,
            target_state TEXT,
            target_locality TEXT,
            time_band TEXT,
            term_family TEXT,
            term TEXT,
            title TEXT,
            snippet TEXT,
            url TEXT NOT NULL,
            stable_id TEXT,
            date_published TEXT,
            inferred_year INTEGER,
            source_stated_place_text TEXT,
            locality_hint TEXT,
            mappability_hint TEXT,
            evidence_source_name TEXT,
            evidence_source_url TEXT,
            access_source_name TEXT,
            access_source_url TEXT,
            original_source_name TEXT,
            rights_status TEXT,
            ethics_status TEXT,
            metadata_only INTEGER DEFAULT 1,
            candidate_score REAL DEFAULT 0,
            duplicate_key TEXT,
            duplicate_status TEXT DEFAULT 'unchecked',
            noise_flags_json TEXT,
            gate_status TEXT DEFAULT 'candidate',
            gate_reasons_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "provisional_records": """
        CREATE TABLE IF NOT EXISTS provisional_records (
            provisional_record_id TEXT PRIMARY KEY,
            run_id TEXT,
            candidate_id TEXT UNIQUE,
            title TEXT NOT NULL,
            summary TEXT,
            date_published TEXT,
            inferred_year INTEGER,
            time_band TEXT,
            target_state TEXT,
            source_stated_place_text TEXT,
            source_name TEXT,
            source_url TEXT NOT NULL,
            evidence_source_name TEXT NOT NULL,
            evidence_source_url TEXT NOT NULL,
            access_source_name TEXT,
            access_source_url TEXT,
            original_source_name TEXT,
            source_tier TEXT,
            route_family TEXT,
            metadata_only INTEGER DEFAULT 1,
            rights_status TEXT,
            ethics_status TEXT,
            provisional_score REAL DEFAULT 0,
            duplicate_key TEXT,
            growth_weight REAL DEFAULT 1.0,
            promotion_status TEXT DEFAULT 'not_reviewed',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "harvest_route_stats": """
        CREATE TABLE IF NOT EXISTS harvest_route_stats (
            run_id TEXT,
            route_id TEXT,
            source_name TEXT,
            state TEXT,
            route_family TEXT,
            pages_fetched INTEGER DEFAULT 0,
            candidates_seen INTEGER DEFAULT 0,
            provisional_records_added INTEGER DEFAULT 0,
            duplicates INTEGER DEFAULT 0,
            noise INTEGER DEFAULT 0,
            robots_blocked INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            yield_score REAL DEFAULT 0,
            recommended_action TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_id, route_id)
        )
    """,
    "harvest_discovered_routes": """
        CREATE TABLE IF NOT EXISTS harvest_discovered_routes (
            discovered_route_id TEXT PRIMARY KEY,
            run_id TEXT,
            discovered_from_route_id TEXT,
            discovered_from_url TEXT,
            candidate_source_name TEXT,
            candidate_url TEXT NOT NULL,
            state_guess TEXT,
            route_family_guess TEXT,
            source_tier_guess TEXT,
            collection_mode_guess TEXT,
            evidence_or_discovery_guess TEXT,
            confidence REAL DEFAULT 0,
            status TEXT DEFAULT 'route_candidate',
            reason_discovered TEXT,
            robots_status TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "harvest_milestones": """
        CREATE TABLE IF NOT EXISTS harvest_milestones (
            run_id TEXT,
            milestone_name TEXT,
            milestone_value INTEGER,
            reached_at TEXT,
            report_path TEXT,
            audit_status TEXT,
            notes TEXT,
            PRIMARY KEY (run_id, milestone_name)
        )
    """,
}

INDEX_SQL = {
    "idx_harvest_frontier_status_priority": "CREATE INDEX IF NOT EXISTS idx_harvest_frontier_status_priority ON harvest_frontier(status, priority_score)",
    "idx_harvest_frontier_route_id": "CREATE INDEX IF NOT EXISTS idx_harvest_frontier_route_id ON harvest_frontier(route_id)",
    "idx_harvest_pages_route_id": "CREATE INDEX IF NOT EXISTS idx_harvest_pages_route_id ON harvest_pages(route_id)",
    "idx_harvest_candidates_run_id": "CREATE INDEX IF NOT EXISTS idx_harvest_candidates_run_id ON harvest_candidates(run_id)",
    "idx_harvest_candidates_duplicate_key": "CREATE INDEX IF NOT EXISTS idx_harvest_candidates_duplicate_key ON harvest_candidates(duplicate_key)",
    "idx_provisional_records_run_id": "CREATE INDEX IF NOT EXISTS idx_provisional_records_run_id ON provisional_records(run_id)",
    "idx_provisional_records_duplicate_key": "CREATE INDEX IF NOT EXISTS idx_provisional_records_duplicate_key ON provisional_records(duplicate_key)",
    "idx_provisional_records_inferred_year": "CREATE INDEX IF NOT EXISTS idx_provisional_records_inferred_year ON provisional_records(inferred_year)",
    "idx_provisional_records_target_state": "CREATE INDEX IF NOT EXISTS idx_provisional_records_target_state ON provisional_records(target_state)",
    "idx_harvest_route_stats_run_yield": "CREATE INDEX IF NOT EXISTS idx_harvest_route_stats_run_yield ON harvest_route_stats(run_id, yield_score)",
}


def expected_columns(sql: str) -> list[tuple[str, str]]:
    conn = sqlite3.connect(":memory:")
    conn.execute(sql)
    table_name = sql.split("CREATE TABLE IF NOT EXISTS", 1)[1].split("(", 1)[0].strip()
    rows = [(row[1], row[2] or "TEXT") for row in conn.execute(f"PRAGMA table_info({table_name})")]
    conn.close()
    return rows


def migrate(db_path: Path) -> dict[str, list[str]]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    existing: list[str] = []
    added_columns: list[str] = []
    created_indexes: list[str] = []
    with sqlite3.connect(db_path) as conn:
        for table, sql in TABLE_SQL.items():
            was_present = table_exists(conn, table)
            conn.execute(sql)
            if was_present:
                existing.append(table)
            else:
                created.append(table)
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
    return {"created_tables": created, "existing_tables": existing, "added_columns": added_columns, "created_indexes": created_indexes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    summary = migrate(Path(args.db))
    print({"generated": now_iso(), **{key: len(value) for key, value in summary.items()}})


if __name__ == "__main__":
    main()
