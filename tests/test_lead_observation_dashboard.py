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


def test_lead_observation_dashboard_keeps_strict_closed_and_no_new_crawl():
    mod = load("lead_observation_dashboard_mod", "build_lead_observation_dashboard.py")
    mig = load("lead_observation_migrate", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            for index in range(3):
                conn.execute(
                    """
                    INSERT INTO target_gap_leads
                    (lead_id, lead_type, route_family, priority_bucket, duplicate_status, constraint_blocker, evidence_gap, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (f"l{index}", "ITEM_DETAIL_REQUIRED_LEAD", "state_library_catalogue", "PRIORITY_LEAD", "unique", "missing_date", "missing_date", "now", "now"),
                )
            conn.commit()
        summary = mod.dashboard(db, tmp_path / "dashboard.md")
        text = (tmp_path / "dashboard.md").read_text()
        assert summary["priority_leads"] == 3
        assert "Strict records mode should remain closed." in text
        assert "do not run more lead crawling yet" in text
        assert "inspect CSV" not in text
