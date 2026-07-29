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
    spec = importlib.util.spec_from_file_location("structured_operator_mod", scripts / "run_structured_endpoint_gap_operator.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_process_query_stages_only_provisional_not_public():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        mod.migrate(db)
        record = mod.EndpointRecord("https://library.example/item/1", "1", "Ghost 1935", "A haunted station item", date_text="1935")

        class FakeClient:
            def fetch_records(self, endpoint, query):
                return [record]

        old_client_for = mod.client_for
        mod.client_for = lambda endpoint_type, cfg, session: FakeClient()
        try:
            row = {
                "endpoint_id": "ep1",
                "endpoint_query_id": "q1",
                "route_id": "r1",
                "source_id": "s1",
                "source_name": "State Library",
                "source_tier": "A",
                "route_family": "state_library_catalogue",
                "state": "WA",
                "endpoint_type": "OAI_PMH",
                "endpoint_url": "https://library.example/oai",
                "query_text": "ghost",
                "controlled_term": "ghost",
                "target_state": "WA",
                "locality": "Albany",
            }
            config = {"target_queries": {"controlled_terms": ["ghost"]}, "temporal_gate": {"min_date_confidence": 0.7}}
            with sqlite3.connect(db) as conn:
                stats = mod.process_query(conn, row, config, "run", None, True)
                conn.commit()
                provisional = conn.execute("SELECT COUNT(*) FROM provisional_records WHERE run_id='run' AND harvest_mode='structured_endpoint_gap'").fetchone()[0]
                public_table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='records'").fetchone()
            assert stats["target_gap_records"] == 1
            assert provisional == 1
            assert public_table is None
        finally:
            mod.client_for = old_client_for
