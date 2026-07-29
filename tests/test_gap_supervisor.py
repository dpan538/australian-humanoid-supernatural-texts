import importlib.util
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel, name):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(name, scripts / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_gap_stop_counts_only_target_gap_eligible_not_auxiliary_growth():
    mig = load(Path("migrate_autoharvest_gap_v2.py"), "gap_supervisor_mig_test")
    sup = load(Path("autoharvest_gap_supervisor.py"), "gap_supervisor_test")
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "db.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO harvest_frontier(frontier_id, run_id, route_id, url, status, discovered_at) VALUES ('f1','run','r','https://example.test','queued','now')")
            for i in range(100):
                conn.execute(
                    """
                    INSERT INTO provisional_records(
                        provisional_record_id, run_id, candidate_id, title, source_url,
                        evidence_source_name, evidence_source_url, target_gap_eligible,
                        auxiliary_status, target_effective_weight, created_at, updated_at
                    )
                    VALUES (?, 'run', ?, 'aux', 'https://example.test', 'Source', 'https://example.test', 0, 'UNDATED_AUXILIARY', 0, 'now', 'now')
                    """,
                    (f"p{i}", f"c{i}"),
                )
            stop, reason = sup.gap_should_stop(conn, "run", 10, time.time(), 168, {"quality_brakes": {"stop_if_target_gap_records_below_after_pages": {"pages": 500, "min_target_records": 10}}})
            assert not stop
            conn.execute("UPDATE provisional_records SET target_gap_eligible=1, target_effective_weight=1 WHERE provisional_record_id='p0'")
            stop, reason = sup.gap_should_stop(conn, "run", 1, time.time(), 168, {"quality_brakes": {"stop_if_target_gap_records_below_after_pages": {"pages": 500, "min_target_records": 10}}})
            assert stop
            assert reason == "target_gap_reached"


def test_gap_supervisor_stops_after_500_pages_with_fewer_than_10_targets():
    mig = load(Path("migrate_autoharvest_gap_v2.py"), "gap_supervisor_mig_test2")
    sup = load(Path("autoharvest_gap_supervisor.py"), "gap_supervisor_test2")
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "db.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO harvest_frontier(frontier_id, run_id, route_id, url, status, discovered_at) VALUES ('f1','run','r','https://example.test','queued','now')")
            for i in range(500):
                conn.execute("INSERT INTO harvest_pages(page_id, run_id, url, fetched_at) VALUES (?, 'run', 'https://example.test', 'now')", (f"page{i}",))
            stop, reason = sup.gap_should_stop(conn, "run", 2000, time.time(), 168, {"quality_brakes": {"stop_if_target_gap_records_below_after_pages": {"pages": 500, "min_target_records": 10}}})
            assert stop
            assert reason == "target_gap_yield_nonviable_after_500_pages"
