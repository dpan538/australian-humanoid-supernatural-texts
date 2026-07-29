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


def test_watchdog_detects_policy_violations_and_stops_run():
    mig = load("migrate_autoharvest_v1_watch", Path("migrate_autoharvest_v1.py"))
    watch = load("autoharvest_watchdog_test", Path("autoharvest_watchdog.py"))
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        db = base / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE records(record_id TEXT)")
            conn.execute("INSERT INTO records VALUES ('r1')")
            conn.execute("INSERT INTO records VALUES ('r2')")
            conn.execute("INSERT INTO harvest_runs(run_id, status, started_at, notes) VALUES ('run','running','now','baseline_public_records:1')")
            conn.execute("INSERT INTO harvest_frontier(frontier_id, run_id, route_id, url, status, robots_status, discovered_at) VALUES ('api','run','api','https://api.trove.nla.gov.au/v3/result','queued','', 'now')")
            conn.execute("INSERT INTO harvest_frontier(frontier_id, run_id, route_id, url, status, robots_status, discovered_at) VALUES ('robots','run','r','https://example.test','fetched','blocked', 'now')")
            conn.execute(
                """
                INSERT INTO provisional_records (
                    provisional_record_id, run_id, candidate_id, title, source_url,
                    evidence_source_name, evidence_source_url, ethics_status, rights_status,
                    created_at, updated_at
                )
                VALUES ('p','run','c','Title','https://example.test','Source','https://example.test','sensitive','metadata_only','now','now')
                """
            )
            conn.commit()
        summary = watch.run_watchdog(db, "run", base / "watch.md")
        assert summary["safety_stopped"]
        text = (base / "watch.md").read_text(encoding="utf-8")
        assert "api_route_use" in text
        assert "sensitive_route_leakage" in text
        assert "robots_violation" in text
        assert "public_records_count_changed" in text
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT status FROM harvest_runs WHERE run_id='run'").fetchone()[0] == "safety_stopped"
