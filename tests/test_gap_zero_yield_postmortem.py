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


def test_zero_yield_breakdown_and_near_misses():
    mig = load(Path("migrate_autoharvest_gap_v2.py"), "postmortem_mig_test")
    post = load(Path("analyze_gap_zero_yield.py"), "postmortem_test")
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "db.sqlite"
        out = Path(temp) / "post"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            rows = [
                ("c1", "r1", "ghost item", "ghost story", "missing_explicit_target_temporal_evidence", 1, 0, 0.8),
                ("c2", "r1", "1964 item", "local history 1964", "missing_controlled_term", 0, 1, 0.8),
                ("c3", "r2", "directory ghost 1964", "search results ghost 1964", "not_item_level:directory", 1, 1, 0.2),
            ]
            for c, r, title, snippet, reasons, term, date, item in rows:
                conn.execute(
                    """
                    INSERT INTO harvest_candidates(candidate_id, run_id, route_id, source_name, source_tier, route_family, title, snippet, url, evidence_source_name, evidence_source_url, duplicate_status, gate_reasons_json, term_hit_confidence, date_confidence, item_level_confidence, created_at, updated_at)
                    VALUES (?, 'run', ?, 'Source', 'A', 'local_history_serial', ?, ?, 'https://example.test', 'Source', 'https://example.test', 'unique', ?, ?, ?, ?, 'now', 'now')
                    """,
                    (c, r, title, snippet, '["' + reasons + '"]', term, date, item),
                )
            for i in range(21):
                conn.execute("INSERT INTO provisional_records(provisional_record_id, run_id, candidate_id, title, source_url, evidence_source_name, evidence_source_url, route_id, target_gap_eligible, auxiliary_status, created_at, updated_at) VALUES (?, 'run', ?, 'aux', 'https://example.test', 'Source', 'https://example.test', 'r1', 0, 'UNDATED_AUXILIARY', 'now', 'now')", (f"p{i}", f"pc{i}"))
        summary = post.analyze(db, "run", out)
        assert summary["near_misses"] >= 3
        near = (out / "near_miss_candidates.csv").read_text(encoding="utf-8")
        assert "TERM_NO_DATE" in near
        assert "DATE_NO_TERM" in near
        assert "DATE_TERM_NOT_ITEM_LEVEL" in near
        routes = (out / "route_failure_breakdown.csv").read_text(encoding="utf-8")
        assert "PAUSE_AUXILIARY_ONLY_ROUTE" in routes
