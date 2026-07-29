#!/usr/bin/env python3
"""Create canonical ID and URL redirect registry tables."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import index_exists, now_iso, table_exists


TABLES = {
    "canonical_id_redirects": """
        CREATE TABLE IF NOT EXISTS canonical_id_redirects (
            redirect_id TEXT PRIMARY KEY,
            redirect_type TEXT,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            from_slug TEXT,
            to_slug TEXT,
            source_table TEXT,
            target_table TEXT,
            reason TEXT,
            confidence REAL DEFAULT 1.0,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "canonical_url_redirects": """
        CREATE TABLE IF NOT EXISTS canonical_url_redirects (
            redirect_id TEXT PRIMARY KEY,
            from_url TEXT NOT NULL,
            to_url TEXT NOT NULL,
            url_role TEXT,
            source_name TEXT,
            redirect_status TEXT,
            http_status_chain TEXT,
            reason TEXT,
            confidence REAL DEFAULT 1.0,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
}

INDEXES = {
    "idx_canonical_id_redirects_from": "CREATE INDEX IF NOT EXISTS idx_canonical_id_redirects_from ON canonical_id_redirects(from_id)",
    "idx_canonical_url_redirects_from": "CREATE INDEX IF NOT EXISTS idx_canonical_url_redirects_from ON canonical_url_redirects(from_url)",
}


def migrate(db_path: Path) -> dict[str, object]:
    created = []
    indexes = []
    with sqlite3.connect(db_path) as conn:
        for name, sql in TABLES.items():
            existed = table_exists(conn, name)
            conn.execute(sql)
            if not existed:
                created.append(name)
        for name, sql in INDEXES.items():
            existed = index_exists(conn, name)
            conn.execute(sql)
            if not existed:
                indexes.append(name)
        conn.commit()
    return {"generated": now_iso(), "created_tables": created, "created_indexes": indexes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    print(migrate(Path(args.db)))


if __name__ == "__main__":
    main()
