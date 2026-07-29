import importlib.util
import sqlite3
import sys
import tempfile
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


def test_gap_rebalance_boosts_target_and_pauses_auxiliary_only():
    mig = load(Path("migrate_autoharvest_gap_v2.py"), "gap_rebalance_mig_test")
    reb = load(Path("autoharvest_gap_rebalance.py"), "gap_rebalance_test")
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "db.sqlite"
        out = Path(temp) / "rebalance.md"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO harvest_frontier(frontier_id, run_id, route_id, url, status, priority_score, discovered_at) VALUES ('f1','run','target','https://a.test','queued',10,'now')")
            conn.execute("INSERT INTO harvest_frontier(frontier_id, run_id, route_id, url, status, priority_score, discovered_at) VALUES ('f2','run','aux','https://b.test','queued',10,'now')")
            conn.execute("INSERT INTO provisional_records(provisional_record_id, run_id, candidate_id, title, source_url, evidence_source_name, evidence_source_url, route_family, target_gap_eligible, target_effective_weight, created_at, updated_at) VALUES ('p1','run','c1','target','https://a.test','A','https://a.test','local_history_serial',1,1,'now','now')")
            for i in range(20):
                conn.execute("INSERT INTO provisional_records(provisional_record_id, run_id, candidate_id, title, source_url, evidence_source_name, evidence_source_url, route_family, target_gap_eligible, target_effective_weight, created_at, updated_at) VALUES (?, 'run', ?, 'aux','https://b.test','B','https://b.test','local_history_serial',0,0,'now','now')", (f"pa{i}", f"ca{i}"))
            conn.execute("UPDATE provisional_records SET route_id='target' WHERE provisional_record_id='p1'")
            conn.execute("UPDATE provisional_records SET route_id='aux' WHERE provisional_record_id!='p1'")
        summary = reb.rebalance(db, Path(temp) / "config.yml", "run", out)
        with sqlite3.connect(db) as conn:
            target_priority = conn.execute("SELECT priority_score FROM harvest_frontier WHERE route_id='target'").fetchone()[0]
            aux_status = conn.execute("SELECT status FROM harvest_frontier WHERE route_id='aux'").fetchone()[0]
        assert target_priority > 10
        assert aux_status == "paused"
        assert summary["boosted"] >= 1
