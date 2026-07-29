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
    spec = importlib.util.spec_from_file_location("query_rebuild_mod", scripts / "rebuild_structured_queries_from_materialized_near_misses.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def add_near(conn, near_id, run_id, endpoint_id, near_type, title, year="", item_url="https://example.org/item"):
    conn.execute(
        """
        INSERT INTO structured_endpoint_near_misses (
            near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier,
            endpoint_type, route_family, item_url, title, description, inferred_year,
            near_miss_type, recoverability_score, recovery_action, recovery_status,
            detail_url, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 'Test Source', 'A', 'WORDPRESS_REST', 'museum_heritage_page',
                ?, ?, 'desc', ?, ?, 90, 'FETCH_DETAIL_PAGE', 'queued', ?, 'now', 'now')
        """,
        (near_id, run_id, near_id.replace("n", "r"), endpoint_id, item_url, title, year, near_type, item_url),
    )


def test_rebuild_queries_from_near_miss_types():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        run_id = "run"
        new_run = "new"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, source_name, source_tier, route_family, state, status, noauth_verified, discovered_at) VALUES ('ep','https://example.org/search?q={query}','WORDPRESS_REST','Test Source','A','museum_heritage_page','WA','active',1,'now')")
            add_near(conn, "n_term", run_id, "ep", "TERM_NO_DATE", "ghost Albany")
            add_near(conn, "n_date", run_id, "ep", "DATE_NO_TERM", "Albany archive", 1935)
            add_near(conn, "n_detail", run_id, "ep", "ITEM_URL_NEEDS_DETAIL", "detail first")
            add_near(conn, "n_field", run_id, "ep", "FIELD_MAPPING_SUSPECT", "field issue")
            conn.commit()
        summary = mod.rebuild(db, run_id, new_run, tmp_path / "report.md", True)
        with sqlite3.connect(db) as conn:
            queries = [row[0] for row in conn.execute("SELECT query_text FROM noauth_endpoint_queries WHERE run_id=?", (new_run,)).fetchall()]
        assert summary["queries_written"] > 0
        assert any("1930s" in query or "1950s" in query for query in queries)
        assert any("ghost" in query.lower() and "1935" in query for query in queries)
        report = (tmp_path / "report.csv").read_text(encoding="utf-8")
        assert "detail enrichment prioritized" in report
        assert "adapter repair prioritized" in report
