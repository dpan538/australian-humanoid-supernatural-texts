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


def test_closeout_aggregates_runs_and_discourages_equivalent_crawlers():
    mod = load("strict_closeout_mod", "finalize_strict_no_credential_closeout.py")
    mig = load("lead_migrate_closeout", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.ROOT = tmp_path
        db = tmp_path / "test.sqlite"
        config = ROOT / "config" / "constraint_decision.yml"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, status, discovered_at) VALUES ('ep','https://example.org/feed','RSS_ATOM','active','now')")
            conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, target_gap_eligible, created_at) VALUES ('r','run','ep','Source','A','RSS_ATOM','https://example.org/item','Ghost lead',0,'now')")
            conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, created_at, updated_at) VALUES ('n','run','r','ep','Source','A','RSS_ATOM','https://example.org/item','Ghost lead','RSS_ITEM_DETAIL_REQUIRED',90,'STILL_ITEM_URL_NEEDS_DETAIL','now','now')")
            conn.commit()
        summary = mod.closeout(db, config, tmp_path / "closeout")
        text = (tmp_path / "closeout" / "strict_no_credential_closeout.md").read_text(encoding="utf-8")
        assert summary["strict_target_gap_records"] == 0
        assert summary["watchdog_hard_violations"] == 0
        assert summary["status"] == "robots_uncertainty_blocked_current_surface_exhausted"
        assert "Continuing equivalent no-auth crawlers is not recommended" in text
