import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(name, scripts / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def insert(conn, lead_id, title="", description="", url="", route_family=""):
    conn.execute(
        """
        INSERT INTO target_gap_leads
        (lead_id, lead_type, title, description, url, route_family, term_signal, evidence_gap, constraint_blocker, created_at, updated_at)
        VALUES (?,?,?,?,? ,?,'ghost','missing_date','missing_date','now','now')
        """,
        (lead_id, "ITEM_DETAIL_REQUIRED_LEAD", title, description, url, route_family),
    )


def test_date_salvage_from_existing_metadata_only():
    mod = load("date_salvage_mod", "salvage_missing_dates_from_leads.py")
    mig = load("date_salvage_migrate", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            insert(conn, "title", title="Haunted railway 1935")
            insert(conn, "decade", description="Ghost stories from the 1960s")
            insert(conn, "url", url="https://example.org/local-history-1958.pdf")
            insert(conn, "serial", title="Newsletter June 1964")
            insert(conn, "modern", description="crawl date 1964 export date")
            insert(conn, "route", description="route target year 1955", route_family="state_library_catalogue")
            conn.commit()
        summary = mod.salvage(db, tmp_path / "date.md", True)
        with sqlite3.connect(db) as conn:
            rows = {row[0]: row[1] for row in conn.execute("SELECT lead_id, temporal_signal FROM target_gap_leads")}
        assert summary["dates_salvaged"] == 4
        assert rows["title"] == "1935"
        assert rows["decade"] == "1960s"
        assert rows["url"] == "1958"
        assert rows["serial"] == "1964"
        assert rows["modern"] in {"", None}
        assert rows["route"] in {"", None}
