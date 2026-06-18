"""Source seeding and lookup helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .utils import PROJECT_ROOT, read_yaml


DEFAULT_SOURCES_PATH = PROJECT_ROOT / "config" / "sources.yml"


def seed_sources(conn: sqlite3.Connection, sources_path: str | Path = DEFAULT_SOURCES_PATH) -> None:
    config = read_yaml(sources_path)
    for source in config.get("sources", []):
        existing = conn.execute(
            "SELECT source_id FROM sources WHERE source_name = ?",
            (source["source_name"],),
        ).fetchone()
        values = (
            source["source_name"],
            source["source_type"],
            source.get("base_url"),
            source.get("access_method"),
            source.get("publicness_level"),
            source.get("ethics_notes"),
        )
        if existing:
            conn.execute(
                """
                UPDATE sources
                SET source_type = ?, base_url = ?, access_method = ?,
                    publicness_level = ?, ethics_notes = ?
                WHERE source_id = ?
                """,
                values[1:] + (existing["source_id"],),
            )
        else:
            conn.execute(
                """
                INSERT INTO sources (
                    source_name, source_type, base_url, access_method,
                    publicness_level, ethics_notes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )


def get_source_id(conn: sqlite3.Connection, source_name: str) -> int:
    row = conn.execute(
        "SELECT source_id FROM sources WHERE source_name = ?",
        (source_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown source_name: {source_name}")
    return int(row["source_id"])


def get_or_create_manual_source(conn: sqlite3.Connection, source_name: str) -> int:
    row = conn.execute(
        "SELECT source_id FROM sources WHERE source_name = ?",
        (source_name,),
    ).fetchone()
    if row:
        return int(row["source_id"])
    cursor = conn.execute(
        """
        INSERT INTO sources (
            source_name, source_type, access_method, publicness_level, ethics_notes
        ) VALUES (?, 'manual', 'manual_import', 'open_full_text',
                  'Manual source added during CSV import; verify publicness before export.')
        """,
        (source_name,),
    )
    return int(cursor.lastrowid)

