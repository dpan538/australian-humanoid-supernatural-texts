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
    spec = importlib.util.spec_from_file_location("adapter_debug_mod", scripts / "debug_structured_endpoint_adapters.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_adapter_debug_flags_wa_atom_and_zero_record_endpoints():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        run_id = "run"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, source_name, source_tier, route_family, state, status, noauth_verified, discovered_at) VALUES ('atom','https://museum.example','ATOM_AtoM','Western Australian Museum','A','museum_heritage_page','WA','active',1,'now')")
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, source_name, source_tier, route_family, state, status, noauth_verified, discovered_at) VALUES ('wp','https://wp.example','WORDPRESS_REST','Zero WP','A','museum_heritage_page','WA','paused',1,'now')")
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, source_name, source_tier, route_family, state, status, noauth_verified, discovered_at) VALUES ('om','https://om.example','OMEKA_API','Zero Omeka','A','museum_heritage_page','WA','paused',1,'now')")
            for idx in range(5):
                conn.execute(
                    """
                    INSERT INTO noauth_endpoint_records (
                        endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type,
                        item_url, title, description, inferred_year, controlled_term_hits,
                        target_gap_eligible, gate_reasons_json, created_at
                    )
                    VALUES (?, ?, 'atom', 'Western Australian Museum', 'A', 'ATOM_AtoM', ?, 'Skip to Content', 'Skip to Content', 1935, '[]', 0, '["not_item_level"]', 'now')
                    """,
                    (f"r{idx}", f"{run_id}", f"https://museum.example/item/{idx}"),
                )
            conn.commit()
        summary = mod.debug(db, run_id, tmp_path / "debug")
        recs = (tmp_path / "debug" / "source_route_adapter_recommendations.csv").read_text(encoding="utf-8")
        coverage = (tmp_path / "debug" / "field_mapping_coverage.csv").read_text(encoding="utf-8")
        assert summary["records"] == 5
        assert "fix_atomt_anchor_filter_and_detail_page_parser" in recs
        assert "adapter_or_query_repair_or_pause_zero_record_endpoint" in recs
        assert "ATOM_AtoM" in coverage
