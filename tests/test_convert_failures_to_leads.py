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


def test_convert_failures_to_lead_types_without_public_mutation():
    mod = load("convert_leads_mod", "convert_failures_to_target_gap_leads.py")
    mig = load("lead_migrate_convert", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS records (record_id TEXT PRIMARY KEY, title TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS map_flags (flag_id TEXT PRIMARY KEY)")
            conn.execute("INSERT INTO records VALUES ('pub','Public')")
            conn.execute("INSERT INTO map_flags VALUES ('map')")
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, status, discovered_at) VALUES ('ep','https://example.org/feed','RSS_ATOM','active','now')")
            conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, target_gap_eligible, created_at) VALUES ('r','run','ep','Source','A','RSS_ATOM','https://example.org/item','Ghost lead',0,'now')")
            conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, created_at, updated_at) VALUES ('n','run','r','ep','Source','A','RSS_ATOM','https://example.org/item','Ghost lead','RSS_ITEM_DETAIL_REQUIRED',90,'STILL_ITEM_URL_NEEDS_DETAIL','now','now')")
            base = "candidate_id,run_id,url,title,source_name,source_tier,ethics_status,gate_status,created_at,updated_at"
            conn.execute(f"INSERT INTO harvest_candidates ({base}) VALUES ('d','run','https://d.example','D item','D source','D','','candidate_hold','now','now')")
            conn.execute(f"INSERT INTO harvest_candidates ({base}) VALUES ('disc','run','https://disc.example','Discovery item','Disc','A','','discovery_only','now','now')")
            conn.execute(f"INSERT INTO harvest_candidates ({base}) VALUES ('sens','run','https://sens.example','Sensitive item','Sens','A','sensitive','candidate_hold','now','now')")
            conn.commit()
        mod.robots_by_near_miss = lambda: {"n": {"robots_status": "ROBOTS_UNKNOWN_HTTP_ERROR", "url_issue": ""}}
        summary = mod.convert(db, ROOT / "config" / "constraint_decision.yml", tmp_path / "created.md", True)
        with sqlite3.connect(db) as conn:
            types = {row[0] for row in conn.execute("SELECT lead_type FROM target_gap_leads").fetchall()}
            public_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            map_count = conn.execute("SELECT COUNT(*) FROM map_flags").fetchone()[0]
        assert summary["target_gap_leads"] >= 4
        assert "ROBOTS_BLOCKED_NEAR_MISS" in types
        assert "ACCESS_PLATFORM_DECOMPOSITION_LEAD" in types
        assert "DISCOVERY_ONLY_REPLACEMENT_LEAD" in types
        assert "MANUAL_SENSITIVE_HOLD" in types
        assert public_count == 1
        assert map_count == 1
