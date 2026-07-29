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


def seed_rss_near(db, title="Ghost at Albany", xml=None):
    mig = load("mig_existing_meta", "migrate_structured_near_miss_v1.py")
    mig.migrate(db)
    xml = xml or "<item><title>Ghost at Albany</title><link>https://example.org/item/1</link><description>A haunted station ghost report</description><pubDate>1935</pubDate><category>ghost</category></item>"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS records (record_id TEXT PRIMARY KEY, title TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS map_flags (flag_id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO records VALUES ('public1','Existing')")
        conn.execute("INSERT INTO map_flags VALUES ('map1')")
        conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, source_name, source_tier, endpoint_url, endpoint_type, domain, status, discovered_at) VALUES ('ep','Source','A','https://example.org/feed.xml','RSS_ATOM','example.org','active','now')")
        conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, metadata_json, target_gap_eligible, created_at) VALUES ('r1','run','ep','Source','A','RSS_ATOM','https://example.org/item/1',?, ?, 0, 'now')", (title, json.dumps({"xml_excerpt": xml})))
        conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, detail_url, created_at, updated_at) VALUES ('n1','run','r1','ep','Source','A','RSS_ATOM','https://example.org/item/1',?,'RSS_ITEM_DETAIL_REQUIRED',90,'queued','https://example.org/item/1','now','now')", (title,))
        conn.commit()


def test_existing_metadata_enrichment_stages_target_only_in_provisional():
    mod = load("existing_meta_mod", "enrich_from_existing_endpoint_metadata.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        seed_rss_near(db)
        summary = mod.enrich_existing_metadata(db, "run", tmp_path / "candidates.csv", tmp_path / "report.md", True)
        with sqlite3.connect(db) as conn:
            provisional = conn.execute("SELECT COUNT(*) FROM provisional_records WHERE harvest_mode='structured_existing_metadata_gap' AND target_gap_eligible=1").fetchone()[0]
            public_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            map_count = conn.execute("SELECT COUNT(*) FROM map_flags").fetchone()[0]
        assert summary["target_gap_records"] == 1
        assert provisional == 1
        assert public_count == 1
        assert map_count == 1
        assert "Network fetches performed: `0`" in (tmp_path / "report.md").read_text()


def test_existing_metadata_remaining_gate_date_no_term():
    mod = load("existing_meta_mod_no_term", "enrich_from_existing_endpoint_metadata.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        seed_rss_near(db, title="Albany archive", xml="<item><title>Albany archive</title><description>Local history item</description><pubDate>1935</pubDate></item>")
        summary = mod.enrich_existing_metadata(db, "run", tmp_path / "candidates.csv", tmp_path / "report.md", True)
        assert summary["target_gap_records"] == 0
        assert summary["remaining_by_gate"]["STILL_DATE_NO_TERM"] == 1
