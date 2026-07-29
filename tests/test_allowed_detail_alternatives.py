import importlib.util
import json
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


def seed(db):
    mig = load("mig_allowed_alt", "migrate_structured_near_miss_v1.py")
    mig.migrate(db)
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, source_name, source_tier, endpoint_url, endpoint_type, domain, status, discovered_at) VALUES ('ep','Source','A','https://example.org/feed.xml','RSS_ATOM','example.org','active','now')")
        conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, metadata_json, target_gap_eligible, created_at) VALUES ('r1','run','ep','Source','A','RSS_ATOM','https://example.org/item/ghost','Ghost report',?, 0, 'now')", (json.dumps({"xml_excerpt": "<item><title>Ghost report</title><link>https://example.org/item/ghost</link></item>"}),))
        conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, detail_url, created_at, updated_at) VALUES ('n1','run','r1','ep','Source','A','RSS_ATOM','https://example.org/item/ghost','Ghost report','RSS_ITEM_DETAIL_REQUIRED',90,'queued','https://example.org/item/ghost','now','now')")
        conn.commit()


def test_discover_and_enrich_allowed_detail_alternative():
    discover = load("discover_alt_mod", "discover_allowed_detail_alternatives.py")
    enrich = load("enrich_alt_mod", "enrich_allowed_detail_alternatives.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        seed(db)

        class Allowed:
            robots_status = "ROBOTS_ALLOWED_BUT_FETCH_FAILED"
            robots_url = "https://example.org/robots.txt"
            robots_error = ""
            http_status_if_known = "200"
            allowed = True

        old_discover = discover.diagnose_robots
        discover.diagnose_robots = lambda _url: Allowed()
        try:
            summary = discover.discover(db, "run", tmp_path / "alts.csv", tmp_path / "alts.md", True)
        finally:
            discover.diagnose_robots = old_discover
        assert summary["safe_to_fetch"] == 1

        old_diag = enrich.diagnose_robots
        old_fetch = enrich.fetch_alternative_url
        enrich.ROOT = tmp_path
        enrich.diagnose_robots = lambda _url: Allowed()
        enrich.fetch_alternative_url = lambda _url, _session, timeout=10.0: (200, '<script type="application/ld+json">{"name":"Ghost report","description":"A haunted hotel ghost story","datePublished":"1935","keywords":"ghost"}</script>', "text/html")
        try:
            enriched = enrich.enrich_alternatives(db, tmp_path / "alts.csv", "run", 10, True)
        finally:
            enrich.diagnose_robots = old_diag
            enrich.fetch_alternative_url = old_fetch
        with sqlite3.connect(db) as conn:
            provisional = conn.execute("SELECT COUNT(*) FROM provisional_records WHERE harvest_mode='structured_allowed_detail_gap' AND target_gap_eligible=1").fetchone()[0]
        assert enriched["target_gap_records"] == 1
        assert provisional == 1
