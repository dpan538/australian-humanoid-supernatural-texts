import csv
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


def seed_near(db, run_id="run", detail_url="https://example.org/item/1", endpoint_type="RSS_ATOM"):
    mig = load("mig_robots_audit", "migrate_structured_near_miss_v1.py")
    mig.migrate(db)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, source_name, source_tier, endpoint_url, endpoint_type, domain, status, discovered_at) VALUES ('ep','Source','A','https://example.org/feed.xml',?, 'example.org','active','now')", (endpoint_type,))
        conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, metadata_json, target_gap_eligible, created_at) VALUES ('r1', ?, 'ep','Source','A',?, ?, 'Ghost item', '{}', 0, 'now')", (run_id, endpoint_type, detail_url))
        conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, detail_url, created_at, updated_at) VALUES ('n1', ?, 'r1', 'ep', 'Source', 'A', ?, ?, 'Ghost item', 'RSS_ITEM_DETAIL_REQUIRED', 90, 'queued', ?, 'now', 'now')", (run_id, endpoint_type, detail_url, detail_url))
        conn.commit()


def test_audit_distinguishes_robots_unknown_and_safe_path():
    mod = load("robots_audit_mod", "audit_near_miss_robots_block.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        seed_near(db)

        class Diag:
            robots_status = "ROBOTS_UNKNOWN_MISSING_ROBOTS"
            robots_url = "https://example.org/robots.txt"
            robots_error = "robots_missing"
            http_status_if_known = "404"
            allowed = False

        old = mod.diagnose_robots
        mod.diagnose_robots = lambda _url: Diag()
        try:
            summary = mod.audit(db, "run", tmp_path / "audit")
        finally:
            mod.diagnose_robots = old
        assert summary["robots_status_counts"]["ROBOTS_UNKNOWN_MISSING_ROBOTS"] == 1
        rows = list(csv.DictReader((tmp_path / "audit" / "robots_block_audit.csv").open()))
        assert rows[0]["can_fetch_detail_safely"] == "false"
        assert rows[0]["recommended_recovery_path"] == "USE_RSS_INLINE_CONTENT"


def test_audit_flags_duplicate_endpoint_detail_url():
    mod = load("robots_audit_mod_dup", "audit_near_miss_robots_block.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        seed_near(db, detail_url="https://example.org/feed.xml")
        summary = mod.audit(db, "run", tmp_path / "audit")
        assert summary["url_issue_counts"]["DETAIL_URL_DUPLICATE_OF_ENDPOINT"] == 1
