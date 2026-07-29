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
    spec = importlib.util.spec_from_file_location("structured_enrichment_operator_mod", scripts / "run_structured_endpoint_enrichment_operator.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_operator_runs_phases_rebuilds_when_recoverable_and_keeps_public_tables():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.BASE_DIR = tmp_path / "processed"
        mod.REVIEW_DIR = tmp_path / "review"
        db = tmp_path / "test.sqlite"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS records (record_id TEXT PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS map_flags (flag_id TEXT PRIMARY KEY)")
            conn.execute("INSERT INTO records VALUES ('r')")
            conn.execute("INSERT INTO map_flags VALUES ('m')")
            conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, source_name, source_tier, endpoint_type, near_miss_type, recoverability_score, recovery_status, created_at, updated_at) VALUES ('n','base','S','A','RSS_ATOM','RSS_ITEM_DETAIL_REQUIRED',90,'queued','now','now')")
            conn.commit()
        calls = []
        mod.audit_metrics = lambda db_path, run_id, out_dir: calls.append("audit") or {"near_record_level": 1}
        mod.materialize_near_misses = lambda db_path, run_id, out, report, execute: calls.append("materialize") or {"materialized": 1}
        mod.debug_adapters = lambda db_path, run_id, out_dir: calls.append("debug") or {"records": 1}
        mod.enrich_near_misses = lambda db_path, run_id, limit, execute: calls.append("enrich") or {"enriched_records": 0, "target_gap_records": 0}
        mod.rebuild_queries = lambda db_path, run_id, new_run_id, out, execute: calls.append("rebuild") or {"queries_written": 2}
        mod.run_watchdog = lambda db_path, run_id, out: calls.append("watchdog") or {"hard": 0, "safety_stopped": False}
        summary = mod.operator(db, "base", "op", 2000, True)
        with sqlite3.connect(db) as conn:
            public_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            map_count = conn.execute("SELECT COUNT(*) FROM map_flags").fetchone()[0]
        assert calls[:4] == ["audit", "materialize", "debug", "enrich"]
        assert "rebuild" in calls
        assert summary["stop_status"] == "paused_recoverable_near_misses_remaining"
        assert public_count == 1
        assert map_count == 1


def test_operator_pauses_when_no_targets_and_no_recoverable_near_misses():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.BASE_DIR = tmp_path / "processed"
        mod.REVIEW_DIR = tmp_path / "review"
        db = tmp_path / "test.sqlite"
        mod.migrate(db)
        mod.audit_metrics = lambda db_path, run_id, out_dir: {"near_record_level": 0}
        mod.materialize_near_misses = lambda db_path, run_id, out, report, execute: {"materialized": 0}
        mod.debug_adapters = lambda db_path, run_id, out_dir: {"records": 0}
        mod.enrich_near_misses = lambda db_path, run_id, limit, execute: {"enriched_records": 0, "target_gap_records": 0}
        mod.rebuild_queries = lambda db_path, run_id, new_run_id, out, execute: {"queries_written": 99}
        mod.run_watchdog = lambda db_path, run_id, out: {"hard": 0, "safety_stopped": False}
        summary = mod.operator(db, "base", "op", 2000, True)
        assert summary["stop_status"] == "paused_near_misses_exhausted_no_targets"
        assert summary["rebuilt_queries"]["queries_written"] == 0
