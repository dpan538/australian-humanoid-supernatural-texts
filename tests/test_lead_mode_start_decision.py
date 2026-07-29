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


def seed_leads(conn, total, priority):
    for index in range(total):
        bucket = "PRIORITY_LEAD" if index < priority else "GOOD_LEAD"
        conn.execute(
            "INSERT INTO target_gap_leads (lead_id, lead_type, priority_bucket, duplicate_status, constraint_blocker, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (f"l{index}", "ITEM_DETAIL_REQUIRED_LEAD", bucket, "unique", "missing_date", "now", "now"),
        )
    conn.commit()


def test_lead_mode_start_decision_refuses_when_existing_layer_is_large():
    mod = load("lead_mode_decision_mod", "decide_whether_to_start_lead_mode.py")
    mig = load("lead_mode_decision_migrate", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = tmp_path / "constraint.yml"
        config.write_text("lead_mode:\n  target_leads: 2000\n", encoding="utf-8")
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            seed_leads(conn, 11343, 518)
        summary = mod.decide(db, config, tmp_path / "decision.md")
        assert summary["recommendation"] == "do_not_start_lead_mode_yet"
        assert "already large" in summary["reason"]


def test_lead_mode_start_decision_can_start_later_when_below_target():
    mod = load("lead_mode_decision_mod2", "decide_whether_to_start_lead_mode.py")
    mig = load("lead_mode_decision_migrate2", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config = tmp_path / "constraint.yml"
        config.write_text("lead_mode:\n  target_leads: 2000\n", encoding="utf-8")
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            seed_leads(conn, 10, 5)
        summary = mod.decide(db, config, tmp_path / "decision.md")
        assert summary["recommendation"] == "start_lead_mode_after_preflight"
