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
    spec = importlib.util.spec_from_file_location("lead_operator_mod", scripts / "run_target_gap_lead_mode_operator.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_lead_mode_operator_creates_leads_only_and_stops_at_target():
    mod = load()
    mig_spec = importlib.util.spec_from_file_location("mig_leadop", ROOT / "scripts" / "migrate_target_gap_leads_v1.py")
    mig = importlib.util.module_from_spec(mig_spec)
    assert mig_spec and mig_spec.loader
    sys.modules[mig_spec.name] = mig
    mig_spec.loader.exec_module(mig)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        cfg = tmp_path / "constraint.yml"
        cfg.write_text("outputs:\n  lead_dir: '" + str(tmp_path / "leads") + "'\n", encoding="utf-8")
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS records (record_id TEXT PRIMARY KEY, title TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS map_flags (flag_id TEXT PRIMARY KEY)")
            conn.execute("INSERT INTO records VALUES ('pub','Public')")
            conn.execute("INSERT INTO map_flags VALUES ('map')")
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, status, discovered_at) VALUES ('ep','https://example.org/feed','RSS_ATOM','active','now')")
            conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, target_gap_eligible, created_at) VALUES ('r','run','ep','Source','A','RSS_ATOM','https://example.org/item','Ghost lead',0,'now')")
            conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, created_at, updated_at) VALUES ('n','run','r','ep','Source','A','RSS_ATOM','https://example.org/item','Ghost lead','RSS_ITEM_DETAIL_REQUIRED',90,'STILL_ITEM_URL_NEEDS_DETAIL','now','now')")
            conn.commit()
        summary = mod.run_operator(db, cfg, 1, True)
        with sqlite3.connect(db) as conn:
            leads = conn.execute("SELECT COUNT(*) FROM target_gap_leads").fetchone()[0]
            public_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            map_count = conn.execute("SELECT COUNT(*) FROM map_flags").fetchone()[0]
        assert summary["status"] == "target_leads_reached"
        assert leads >= 1
        assert public_count == 1
        assert map_count == 1
