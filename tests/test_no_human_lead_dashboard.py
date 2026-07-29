import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("lead_dashboard_mod", scripts / "build_no_human_lead_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_dashboard_recommends_lead_mode_without_csv_review_request():
    mod = load()
    mig_spec = importlib.util.spec_from_file_location("mig_dash", ROOT / "scripts" / "migrate_target_gap_leads_v1.py")
    mig = importlib.util.module_from_spec(mig_spec)
    assert mig_spec and mig_spec.loader
    sys.modules[mig_spec.name] = mig
    mig_spec.loader.exec_module(mig)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO target_gap_leads (lead_id, lead_type, title, source_name, route_family, target_state, inferred_year, constraint_blocker, priority_bucket, lead_score, created_at, updated_at) VALUES ('l','ITEM_DETAIL_REQUIRED_LEAD','Ghost','Source','state_library_catalogue','WA',1935,'robots_unknown','PRIORITY_LEAD',90,'now','now')")
            conn.commit()
        summary = mod.dashboard(db, tmp_path / "dashboard.md")
        text = (tmp_path / "dashboard.md").read_text()
        assert summary["leads"] == 1
        assert "Continue strict records mode: `no`" in text
        assert "Lead mode? `available later`" in text
        assert "Start lead mode immediately? `no`" in text
        assert "Metadata-only 1955-1976 layer? `yes`" in text
        assert "make lead-intelligence-all" in text
        assert "inspect CSV" not in text
