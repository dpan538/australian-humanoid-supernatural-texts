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
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def candidate():
    return {
        "run_id": "run",
        "candidate_id": "cand1",
        "title": "Perth ghost local history 1960",
        "snippet": "A local history record",
        "date_published": "1960",
        "inferred_year": 1960,
        "time_band": "1955_1964",
        "target_state": "WA",
        "source_stated_place_text": "Perth",
        "source_name": "WA Local History",
        "url": "https://example.test/record",
        "evidence_source_name": "WA Local History",
        "evidence_source_url": "https://example.test/record",
        "access_source_name": "WA Local History",
        "access_source_url": "https://example.test/",
        "original_source_name": "",
        "source_tier": "A",
        "route_family": "local_history_serial",
        "metadata_only": 1,
        "rights_status": "metadata_only",
        "ethics_status": "not_sensitive",
        "duplicate_key": "dup1",
    }


def test_provisional_record_does_not_write_public_records_or_map_flags_and_dedupes():
    eng = load("autoharvest_engine_prov", Path("lib/autoharvest_engine.py"))
    mig = load("migrate_autoharvest_v1_prov", Path("migrate_autoharvest_v1.py"))
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE records(record_id TEXT, title TEXT)")
            conn.execute("CREATE TABLE narrative_locations(location_id TEXT, public_map INTEGER)")
            before_records = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            before_map = conn.execute("SELECT COUNT(*) FROM narrative_locations").fetchone()[0]
            assert eng.insert_provisional_record(conn, candidate(), 95)
            assert not eng.insert_provisional_record(conn, candidate(), 95)
            assert conn.execute("SELECT COUNT(*) FROM provisional_records").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == before_records
            assert conn.execute("SELECT COUNT(*) FROM narrative_locations").fetchone()[0] == before_map
            row = conn.execute("SELECT growth_weight FROM provisional_records").fetchone()
            assert row[0] == 2.0
