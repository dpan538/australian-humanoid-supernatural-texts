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


def test_lead_blocker_analysis_recommends_by_cluster():
    mod = load("blocker_analysis_mod", "analyze_lead_blockers.py")
    mig = load("blocker_analysis_migrate", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            for index in range(3):
                conn.execute(
                    "INSERT INTO target_gap_leads (lead_id, lead_type, route_family, constraint_blocker, evidence_gap, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                    (f"m{index}", "ITEM_DETAIL_REQUIRED_LEAD", "museum_heritage_page", "missing_date", "missing_date", "now", "now"),
                )
            conn.execute("INSERT INTO target_gap_leads (lead_id, lead_type, route_family, constraint_blocker, evidence_gap, url, created_at, updated_at) VALUES ('r','ROBOTS_BLOCKED_NEAR_MISS','state_library_catalogue','robots_unknown','robots_unknown','https://example.org/a','now','now')")
            conn.commit()
        summary = mod.analyze(db, tmp_path / "blockers.md")
        text = (tmp_path / "blockers.md").read_text()
        assert summary["top_blocker"] == "missing_date"
        assert "`museum_heritage_page`: 3 leads" in text
        assert "date salvage only" in text
        assert "permission/robots clarification" in text
