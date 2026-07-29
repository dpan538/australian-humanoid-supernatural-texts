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


def test_source_intelligence_brief_aggregates_without_row_level_details():
    mod = load("source_brief_mod", "build_source_intelligence_brief.py")
    mig = load("source_brief_migrate", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                INSERT INTO target_gap_leads
                (lead_id, lead_type, title, source_family, route_family, target_state, term_signal, constraint_blocker, priority_bucket, created_at, updated_at)
                VALUES ('a','ITEM_DETAIL_REQUIRED_LEAD','Private row title','museum','museum_heritage_page','WA','ghost','missing_date','GOOD_LEAD','now','now')
                """
            )
            conn.execute(
                """
                INSERT INTO target_gap_leads
                (lead_id, lead_type, title, source_family, route_family, target_state, constraint_blocker, priority_bucket, created_at, updated_at)
                VALUES ('b','ITEM_DETAIL_REQUIRED_LEAD','Another private title','library','state_library_catalogue','TAS','missing_term','PRIORITY_LEAD','now','now')
                """
            )
            conn.commit()
        summary = mod.brief(db, tmp_path / "brief.md")
        text = (tmp_path / "brief.md").read_text()
        assert summary["leads"] == 2
        assert "Rich But Undated Source Families" in text
        assert "Technical vs Structural Blockers" in text
        assert "Private row title" not in text
        assert "Another private title" not in text
