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


def insert(conn, lead_id, title, url, score, source_name="Archive"):
    conn.execute(
        """
        INSERT INTO target_gap_leads
        (lead_id, lead_type, title, url, source_name, lead_score, created_at, updated_at)
        VALUES (?,?,?,?,?,?, 'now', 'now')
        """,
        (lead_id, "ITEM_DETAIL_REQUIRED_LEAD", title, url, source_name, score),
    )


def test_lead_dedupe_clusters_exact_url_and_title_source_without_deleting():
    mod = load("lead_dedupe_mod", "dedupe_target_gap_leads.py")
    mig = load("lead_dedupe_migrate", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            insert(conn, "a", "Ghost item", "https://example.org/items/1", 20)
            insert(conn, "b", "Ghost item duplicate", "https://example.org/items/1", 90)
            insert(conn, "c", "Same Title", "", 70, "State Library")
            insert(conn, "d", "Same  title!", "", 40, "State Library")
            conn.commit()
        summary = mod.dedupe(db, tmp_path / "dedupe.md", True)
        with sqlite3.connect(db) as conn:
            rows = {row[0]: row[1] for row in conn.execute("SELECT lead_id, duplicate_status FROM target_gap_leads")}
            count = conn.execute("SELECT COUNT(*) FROM target_gap_leads").fetchone()[0]
        assert summary["canonical_leads"] == 2
        assert rows["b"] == "canonical"
        assert rows["a"] == "duplicate"
        assert rows["c"] == "canonical"
        assert rows["d"] == "probable_duplicate"
        assert count == 4
        assert (tmp_path / "canonical_target_gap_leads.csv").exists()
        assert (tmp_path / "duplicate_leads.csv").exists()
