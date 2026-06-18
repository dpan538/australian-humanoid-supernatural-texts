"""SQLite connection and initialisation helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import INDEX_STATEMENTS, SCHEMA_STATEMENTS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "processed" / "australian_humanoid_figures.sqlite"


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enabled."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_statements(conn: sqlite3.Connection, statements: Iterable[str]) -> None:
    for statement in statements:
        conn.execute(statement)


def initialise_database(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Create the project database and all expected tables and indexes."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        run_statements(conn, SCHEMA_STATEMENTS)
        run_statements(conn, INDEX_STATEMENTS)
        conn.commit()
    return path


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}

