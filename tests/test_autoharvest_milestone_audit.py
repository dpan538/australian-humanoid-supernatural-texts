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


def test_milestone_audit_writes_promotion_proposal_without_applying():
    mig = load("migrate_autoharvest_v1_audit", Path("migrate_autoharvest_v1.py"))
    audit = load("autoharvest_milestone_audit_test", Path("autoharvest_milestone_audit.py"))
    eng = load("autoharvest_engine_audit", Path("lib/autoharvest_engine.py"))
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        db = base / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE records(record_id TEXT, title TEXT)")
            cand = {
                "run_id": "run", "candidate_id": "cand", "title": "Perth ghost 1960",
                "snippet": "local history", "date_published": "1960", "inferred_year": 1960,
                "time_band": "1955_1964", "target_state": "WA", "source_stated_place_text": "Perth",
                "source_name": "Source", "url": "https://example.test/record",
                "evidence_source_name": "Source", "evidence_source_url": "https://example.test/record",
                "access_source_name": "Source", "access_source_url": "https://example.test/",
                "source_tier": "A", "route_family": "local_history_serial", "metadata_only": 1,
                "rights_status": "metadata_only", "ethics_status": "not_sensitive", "duplicate_key": "dup",
            }
            eng.insert_provisional_record(conn, cand, 90)
            conn.commit()
        out_dir = base / "audit"
        summary = audit.run_audit(db, "run", 1, out_dir)
        assert summary["proposals"] == 1
        assert (out_dir / "promotion_proposal.csv").exists()
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
        assert "Promotion proposal applied: `no`" in (out_dir / "milestone_summary.md").read_text(encoding="utf-8")
