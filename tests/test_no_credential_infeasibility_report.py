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
    spec = importlib.util.spec_from_file_location("infeasibility_mod", scripts / "no_credential_infeasibility_report.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_infeasibility_not_declared_when_near_misses_or_queue_remain():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.ROOT = tmp_path
        db = tmp_path / "test.sqlite"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, status, discovered_at) VALUES ('ep','https://example.org','OAI_PMH','active','now')")
            conn.execute("INSERT INTO noauth_endpoint_queries (endpoint_query_id, run_id, endpoint_id, query_text, status, created_at) VALUES ('q','run','ep','ghost','queued','now')")
            conn.commit()
        summary = mod.report(db, "run", tmp_path / "missing.md", tmp_path / "checkpoint.md", tmp_path / "out.md")
        assert summary["declare_infeasible"] is False
        assert "Do not declare infeasibility yet" in (tmp_path / "out.md").read_text(encoding="utf-8")
