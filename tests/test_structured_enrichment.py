import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_recovery():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("structured_recovery_mod", scripts / "lib" / "structured_endpoint_recovery.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_migrate():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("structured_near_migrate_mod", scripts / "migrate_structured_near_miss_v1.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def base_near(endpoint_type="RSS_ATOM", near_id="near1", detail_url="https://example.org/item"):
    return {
        "near_miss_id": near_id,
        "run_id": "run",
        "endpoint_record_id": "r1",
        "endpoint_id": "ep1",
        "source_name": "State Library",
        "source_tier": "A",
        "endpoint_type": endpoint_type,
        "route_family": "state_library_catalogue",
        "item_url": detail_url,
        "item_id": "item",
        "title": "Summary item",
        "description": "summary",
        "date_text": "",
        "place_text": "Albany",
        "near_miss_type": "RSS_ITEM_DETAIL_REQUIRED",
        "recoverability_score": 90,
        "recovery_action": "FETCH_RSS_ITEM_LINK",
        "recovery_status": "queued",
        "detail_url": detail_url,
    }


def test_detail_parsers_extract_atomt_omeka_wordpress_and_jsonld():
    rec = load_recovery()
    atom_html = "<html><title>Ghost at Albany</title><dl><dt>Date</dt><dd>1935</dd><dt>Scope and content</dt><dd>A haunted station record</dd><dt>Subject</dt><dd>ghost stories</dd></dl></html>"
    atom = rec.parse_html_metadata(atom_html, "https://example.org/atom")
    assert atom["date_text"] == "1935"
    assert "haunted station" in atom["description"]
    assert "ghost stories" in atom["subject_terms"]
    omeka = rec.parse_json_metadata('{"dcterms:title":[{"@value":"Bunyip file"}],"dcterms:date":[{"@value":"1942"}],"dcterms:description":[{"@value":"A bunyip collection item"}],"dcterms:subject":[{"@value":"bunyip"}]}', "OMEKA_API")
    assert omeka["title"] == "Bunyip file"
    assert omeka["date_text"] == "1942"
    wordpress = rec.parse_json_metadata('{"title":{"rendered":"Modern ghost post"},"date":"2024-01-01","content":{"rendered":"Modern page without target date"}}', "WORDPRESS_REST")
    assert wordpress["date_text"].startswith("2024")
    jsonld = rec.parse_html_metadata('<script type="application/ld+json">{"name":"Ghost article","datePublished":"1936","description":"A haunted article"}</script>', "https://example.org/rss")
    assert jsonld["title"] == "Ghost article"
    assert jsonld["date_text"] == "1936"


def test_enriched_target_goes_only_to_provisional_records():
    rec = load_recovery()
    mig = load_migrate()
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS records (record_id TEXT PRIMARY KEY, title TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS map_flags (flag_id TEXT PRIMARY KEY)")
            conn.execute("INSERT INTO records VALUES ('public1','Existing public row')")
            conn.execute("INSERT INTO map_flags VALUES ('map1')")
            near = base_near()
            fields = rec.NEAR_MISS_FIELDS
            conn.execute(f"INSERT INTO structured_endpoint_near_misses ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})", tuple(near.get(field, "") for field in fields))
            conn.commit()

        old_fetch = rec.fetch_url
        rec.fetch_url = lambda url, session, timeout=12.0, rate_limit=0.25: (
            200,
            '<script type="application/ld+json">{"name":"Ghost at Albany station","datePublished":"1935","description":"A haunted station item with ghost evidence","keywords":"ghost"}</script>',
            "text/html",
        )
        try:
            with sqlite3.connect(db) as conn:
                conn.row_factory = sqlite3.Row
                near_row = dict(conn.execute("SELECT * FROM structured_endpoint_near_misses").fetchone())
                result = rec.process_near_miss(conn, near_row, {"target_queries": {"controlled_terms": ["ghost"]}, "temporal_gate": {"min_date_confidence": 0.7}}, "run", None, True)
                conn.commit()
                provisional = conn.execute("SELECT COUNT(*) FROM provisional_records WHERE harvest_mode='structured_endpoint_enriched_gap'").fetchone()[0]
                public_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
                map_count = conn.execute("SELECT COUNT(*) FROM map_flags").fetchone()[0]
            assert result["target_gap_eligible"] == 1
            assert provisional == 1
            assert public_count == 1
            assert map_count == 1
        finally:
            rec.fetch_url = old_fetch


def test_wordpress_modern_post_date_is_not_target_date_without_content_date():
    rec = load_recovery()
    mig = load_migrate()
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        mig.migrate(db)
        near = base_near("WORDPRESS_REST", "nearwp", "https://example.org/post")
        near["near_miss_type"] = "WORDPRESS_POST_DETAIL_REQUIRED"
        near["recovery_action"] = "FETCH_WORDPRESS_POST"
        with sqlite3.connect(db) as conn:
            fields = rec.NEAR_MISS_FIELDS
            conn.execute(f"INSERT INTO structured_endpoint_near_misses ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})", tuple(near.get(field, "") for field in fields))
            conn.commit()
        old_fetch = rec.fetch_url
        rec.fetch_url = lambda url, session, timeout=12.0, rate_limit=0.25: (200, '<meta property="article:published_time" content="2024-01-01"><title>Ghost tour</title><p>Modern ghost tour page.</p>', "text/html")
        try:
            with sqlite3.connect(db) as conn:
                conn.row_factory = sqlite3.Row
                result = rec.process_near_miss(conn, dict(conn.execute("SELECT * FROM structured_endpoint_near_misses").fetchone()), {"target_queries": {"controlled_terms": ["ghost"]}, "temporal_gate": {"min_date_confidence": 0.7}}, "run", None, True)
                conn.commit()
                provisional = conn.execute("SELECT COUNT(*) FROM provisional_records WHERE harvest_mode='structured_endpoint_enriched_gap'").fetchone()[0]
            assert result["target_gap_eligible"] == 0
            assert provisional == 0
        finally:
            rec.fetch_url = old_fetch
