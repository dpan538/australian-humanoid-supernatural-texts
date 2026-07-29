#!/usr/bin/env python3
"""Add collection-expansion V2 staging and audit tables."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import column_exists, index_exists, now_iso, table_exists


REPORT_PATH = ROOT / "data" / "processed" / "v2" / "collection_expansion_migration_report.md"

TABLE_SQL: dict[str, str] = {
    "collection_routes": """
        CREATE TABLE IF NOT EXISTS collection_routes (
            route_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            institution TEXT,
            route_family TEXT,
            source_tier TEXT,
            evidence_or_discovery TEXT,
            scope TEXT,
            states_json TEXT,
            years_likely TEXT,
            access_method TEXT,
            base_url TEXT,
            search_url_template TEXT,
            allowed_content_mode TEXT,
            full_text_allowed INTEGER DEFAULT 0,
            robots_check_required INTEGER DEFAULT 1,
            rate_limit_seconds REAL DEFAULT 2.0,
            temporal_gap_value TEXT,
            regional_balance_value TEXT,
            mappability_likelihood TEXT,
            duplicate_risk TEXT,
            ethics_risk TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "source_chains": """
        CREATE TABLE IF NOT EXISTS source_chains (
            source_chain_id TEXT PRIMARY KEY,
            record_id TEXT,
            narrative_unit_id TEXT,
            candidate_id TEXT,
            discovery_source_name TEXT,
            discovery_source_type TEXT,
            discovery_source_url TEXT,
            access_source_name TEXT,
            access_source_type TEXT,
            access_source_url TEXT,
            original_source_name TEXT,
            original_publication TEXT,
            original_publication_date TEXT,
            evidence_source_name TEXT,
            evidence_source_type TEXT,
            evidence_source_url TEXT,
            evidence_source_family TEXT,
            evidence_source_tier TEXT,
            evidence_strength TEXT,
            rights_status TEXT,
            metadata_only INTEGER DEFAULT 1,
            full_text_available INTEGER DEFAULT 0,
            source_chain_review_status TEXT DEFAULT 'needs_review',
            reviewer_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "collection_route_runs": """
        CREATE TABLE IF NOT EXISTS collection_route_runs (
            run_id TEXT PRIMARY KEY,
            route_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            mode TEXT,
            status TEXT,
            query_count INTEGER DEFAULT 0,
            fetched_count INTEGER DEFAULT 0,
            candidate_count INTEGER DEFAULT 0,
            accepted_count INTEGER DEFAULT 0,
            rejected_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            notes TEXT
        )
    """,
    "collection_candidates": """
        CREATE TABLE IF NOT EXISTS collection_candidates (
            candidate_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            route_id TEXT NOT NULL,
            source_id TEXT,
            source_name TEXT,
            source_tier TEXT,
            evidence_or_discovery TEXT,
            query_string TEXT,
            term_family TEXT,
            time_band TEXT,
            target_state TEXT,
            target_locality TEXT,
            title TEXT,
            publication TEXT,
            author TEXT,
            date_published TEXT,
            inferred_year INTEGER,
            url TEXT,
            stable_id TEXT,
            snippet TEXT,
            raw_text_path TEXT,
            source_stated_place_text TEXT,
            inferred_state TEXT,
            location_role TEXT,
            mappability_hint TEXT,
            ethics_flags_json TEXT,
            rights_status TEXT,
            metadata_only INTEGER DEFAULT 1,
            duplicate_key TEXT,
            duplicate_status TEXT DEFAULT 'unchecked',
            review_status TEXT DEFAULT 'needs_review',
            reviewer_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "geocode_review_queue": """
        CREATE TABLE IF NOT EXISTS geocode_review_queue (
            geocode_review_id TEXT PRIMARY KEY,
            record_id TEXT,
            narrative_unit_id TEXT,
            candidate_id TEXT,
            source_stated_place_text TEXT NOT NULL,
            jurisdiction_state TEXT,
            location_role TEXT,
            place_authority TEXT,
            place_authority_id TEXT,
            gazetteer_match_label TEXT,
            lat REAL,
            lng REAL,
            coordinate_precision TEXT,
            geocode_source TEXT,
            geocode_confidence TEXT DEFAULT 'needs_review',
            display_allowed INTEGER DEFAULT 0,
            display_suppression_reason TEXT,
            ethics_flags_json TEXT,
            review_status TEXT DEFAULT 'needs_review',
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "source_quality_reviews": """
        CREATE TABLE IF NOT EXISTS source_quality_reviews (
            source_quality_review_id TEXT PRIMARY KEY,
            source_id TEXT,
            source_name TEXT NOT NULL,
            institution TEXT,
            source_tier TEXT,
            evidence_or_discovery TEXT,
            review_status TEXT DEFAULT 'needs_review',
            robots_status TEXT,
            terms_status TEXT,
            allowed_content_mode TEXT,
            notes TEXT,
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "release_gate_results": """
        CREATE TABLE IF NOT EXISTS release_gate_results (
            gate_run_id TEXT,
            gate_name TEXT,
            gate_status TEXT,
            observed_value TEXT,
            threshold_value TEXT,
            details TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (gate_run_id, gate_name)
        )
    """,
}

INDEX_SQL = {
    "idx_collection_candidates_run_id": "CREATE INDEX IF NOT EXISTS idx_collection_candidates_run_id ON collection_candidates(run_id)",
    "idx_collection_candidates_route_id": "CREATE INDEX IF NOT EXISTS idx_collection_candidates_route_id ON collection_candidates(route_id)",
    "idx_collection_candidates_inferred_year": "CREATE INDEX IF NOT EXISTS idx_collection_candidates_inferred_year ON collection_candidates(inferred_year)",
    "idx_collection_candidates_target_state": "CREATE INDEX IF NOT EXISTS idx_collection_candidates_target_state ON collection_candidates(target_state)",
    "idx_collection_candidates_review_status": "CREATE INDEX IF NOT EXISTS idx_collection_candidates_review_status ON collection_candidates(review_status)",
    "idx_collection_candidates_duplicate_key": "CREATE INDEX IF NOT EXISTS idx_collection_candidates_duplicate_key ON collection_candidates(duplicate_key)",
    "idx_source_chains_record_id": "CREATE INDEX IF NOT EXISTS idx_source_chains_record_id ON source_chains(record_id)",
    "idx_source_chains_candidate_id": "CREATE INDEX IF NOT EXISTS idx_source_chains_candidate_id ON source_chains(candidate_id)",
    "idx_geocode_review_queue_candidate_id": "CREATE INDEX IF NOT EXISTS idx_geocode_review_queue_candidate_id ON geocode_review_queue(candidate_id)",
    "idx_geocode_review_queue_review_status": "CREATE INDEX IF NOT EXISTS idx_geocode_review_queue_review_status ON geocode_review_queue(review_status)",
}


def expected_columns(sql: str) -> list[tuple[str, str]]:
    conn = sqlite3.connect(":memory:")
    conn.execute(sql)
    table_name = sql.split("CREATE TABLE IF NOT EXISTS", 1)[1].split("(", 1)[0].strip()
    cols = []
    for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall():
        cols.append((row[1], row[2] or "TEXT"))
    conn.close()
    return cols


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

    return {
        "created_tables": created,
        "existing_tables": existing,
        "added_columns": added_columns,
        "created_indexes": created_indexes,
    }


def write_report(summary: dict[str, list[str]], db_path: Path) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Collection Expansion V2 Migration Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Database: `{db_path}`",
        "",
        "## Summary",
        f"- Created tables: `{len(summary['created_tables'])}`",
        f"- Existing tables: `{len(summary['existing_tables'])}`",
        f"- Added columns: `{len(summary['added_columns'])}`",
        f"- Created indexes: `{len(summary['created_indexes'])}`",
        "",
        "## Created Tables",
    ]
    lines.extend([f"- `{name}`" for name in summary["created_tables"]] or ["- None"])
    lines.append("")
    lines.append("## Added Columns")
    lines.extend([f"- `{name}`" for name in summary["added_columns"]] or ["- None"])
    lines.append("")
    lines.append("## Created Indexes")
    lines.extend([f"- `{name}`" for name in summary["created_indexes"]] or ["- None"])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    args = parser.parse_args()

    summary = migrate(Path(args.db))
    write_report(summary, Path(args.db))
    print(
        "Collection expansion migration complete: "
        f"{len(summary['created_tables'])} tables created, "
        f"{len(summary['added_columns'])} columns added, "
        f"{len(summary['created_indexes'])} indexes created."
    )
    print(f"Wrote report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
