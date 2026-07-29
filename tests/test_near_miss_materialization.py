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
    spec = importlib.util.spec_from_file_location("materialize_structured_near_mod", scripts / "materialize_structured_near_misses.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def insert_record(conn, record_id, run_id, endpoint_id, endpoint_type, title, desc, year, hits, item_url="https://example.org/item"):
    conn.execute(
        """
        INSERT INTO noauth_endpoint_records (
            endpoint_record_id, run_id, endpoint_id, endpoint_query_id, source_name, source_tier,
            endpoint_type, item_url, item_id, title, description, inferred_year,
            controlled_term_hits, target_gap_eligible, gate_reasons_json, created_at
        )
        VALUES (?, ?, ?, 'q1', 'Test Source', 'A', ?, ?, ?, ?, ?, ?, ?, 0, '[]', 'now')
        """,
        (record_id, run_id, endpoint_id, endpoint_type, item_url, record_id, title, desc, year, hits),
    )


def test_materializes_near_miss_types_and_recoverability():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        run_id = "run"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            for endpoint_id, endpoint_type in [("ep_oai", "OAI_PMH"), ("ep_atom", "ATOM_AtoM"), ("ep_generic", "PUBLIC_CATALOGUE_JSON")]:
                conn.execute(
                    "INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, source_name, source_tier, route_family, state, status, noauth_verified, discovered_at) VALUES (?,?,?,?,?,?,?,?,1,'now')",
                    (endpoint_id, "https://example.org/search?q={query}", endpoint_type, "Test Source", "A", "museum_heritage_page", "WA", "active"),
                )
            conn.execute("INSERT INTO noauth_endpoint_queries (endpoint_query_id, run_id, endpoint_id, query_text, controlled_term, status, created_at) VALUES ('q1',?,?,?,?,?,?)", (run_id, "ep_oai", "ghost", "ghost", "attempted", "now"))
            insert_record(conn, "term_no_date", run_id, "ep_generic", "PUBLIC_CATALOGUE_JSON", "Ghost story", "haunted item without date", None, '["ghost"]')
            insert_record(conn, "date_no_term", run_id, "ep_generic", "PUBLIC_CATALOGUE_JSON", "Station record", "plain item", 1935, "[]")
            insert_record(conn, "item_url", run_id, "ep_generic", "PUBLIC_CATALOGUE_JSON", "Archive item", "This is a generic catalogue summary that has an item URL but lacks decisive target evidence.", None, "[]")
            insert_record(conn, "atom", run_id, "ep_atom", "ATOM_AtoM", "Archive item", "summary", 1940, "[]")
            conn.commit()
        summary = mod.materialize(db, run_id, tmp_path / "near.csv", tmp_path / "report.md", True)
        with sqlite3.connect(db) as conn:
            rows = conn.execute("SELECT near_miss_type, recoverability_score FROM structured_endpoint_near_misses WHERE run_id=?", (run_id,)).fetchall()
        types = {row[0] for row in rows}
        assert "TERM_NO_DATE" in types
        assert "DATE_NO_TERM" in types
        assert "ITEM_URL_NEEDS_DETAIL" in types
        assert "AtoM_DETAIL_REQUIRED" in types
        assert all(float(row[1]) > 0 for row in rows)
        assert summary["materialized"] == 4
        assert len((tmp_path / "near.csv").read_text(encoding="utf-8").splitlines()) > 1
