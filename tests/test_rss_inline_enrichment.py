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


def test_rss_inline_enrichment_extracts_feed_entry_metadata_without_detail_fetch():
    mod = load("rss_inline_mod", "enrich_rss_items_inline.py")
    mig = load("mig_rss_inline", "migrate_structured_near_miss_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        xml = "<item><title>Ghost report</title><link>https://example.org/item/ghost</link><description>A haunted hotel ghost story</description><dc:date xmlns:dc=\"http://purl.org/dc/elements/1.1/\">1942</dc:date><category>ghost</category></item>"
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, source_name, source_tier, endpoint_url, endpoint_type, domain, status, discovered_at) VALUES ('ep','Source','A','https://example.org/feed.xml','RSS_ATOM','example.org','active','now')")
            conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, metadata_json, target_gap_eligible, created_at) VALUES ('r1','run','ep','Source','A','RSS_ATOM','https://example.org/item/ghost','Ghost report',?, 0, 'now')", (json.dumps({"xml_excerpt": xml}),))
            conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, detail_url, created_at, updated_at) VALUES ('n1','run','r1','ep','Source','A','RSS_ATOM','https://example.org/item/ghost','Ghost report','RSS_ITEM_DETAIL_REQUIRED',90,'queued','https://example.org/item/ghost','now','now')")
            conn.commit()
        old = mod.diagnose_robots
        mod.diagnose_robots = lambda _url: type("D", (), {"robots_status": "ROBOTS_UNKNOWN_MISSING_ROBOTS", "allowed": False})()
        try:
            summary = mod.enrich_rss_inline(db, "run", tmp_path / "rss", True)
        finally:
            mod.diagnose_robots = old
        assert summary["target_gap_records"] == 1
        assert summary["blocked_detail_queue"] == 1
        assert "Network" not in (tmp_path / "rss" / "rss_inline_enrichment_report.md").read_text()
