import sqlite3
import tempfile
from pathlib import Path

from aus_humanoid.db import connect, initialise_database
from aus_humanoid.models import REQUIRED_TABLES


def test_schema_creates_required_tables():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        initialise_database(db_path)
        with connect(db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        names = {row["name"] for row in rows}
    assert set(REQUIRED_TABLES).issubset(names)


def test_schema_enables_foreign_keys():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        initialise_database(db_path)
        with connect(db_path) as conn:
            enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert enabled == 1


def test_schema_has_expected_indexes():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        initialise_database(db_path)
        raw = sqlite3.connect(db_path)
        try:
            rows = raw.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        finally:
            raw.close()
    indexes = {row[0] for row in rows}
    assert "idx_records_year" in indexes
    assert "idx_aliases_alias" in indexes
    assert "idx_queries_query_string" in indexes

