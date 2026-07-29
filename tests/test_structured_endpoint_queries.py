import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("structured_queries_mod", scripts / "build_structured_endpoint_queries.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_queries_prioritizes_endpoint_terms():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        config = tmp_path / "config.yml"
        config.write_text(yaml.safe_dump({"target_queries": {"controlled_terms": ["ghost"], "date_terms": ["1930"], "priority_states": ["WA"], "priority_localities": {"WA": ["Albany"]}}, "endpoint_probe_limits": {"max_queries_per_endpoint": 20}}), encoding="utf-8")
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO noauth_endpoint_inventory (endpoint_id, route_id, source_name, source_tier, state, endpoint_url, endpoint_type, noauth_verified, api_key_required, login_required, paywall_required, status, discovered_at) VALUES ('ep1','r1','State Library','A','WA','https://example.org/search?q={query}','WORDPRESS_REST',1,0,0,0,'active','now')"
            )
            conn.commit()
        summary = mod.build(db, config, "run", tmp_path / "report.md", True)
        assert summary["queries"] > 0
        with sqlite3.connect(db) as conn:
            rows = conn.execute("SELECT query_text, target_state, priority_score FROM noauth_endpoint_queries").fetchall()
        assert any("Albany" in row[0] for row in rows)
        assert all(row[1] == "WA" for row in rows)
        assert max(row[2] for row in rows) > 0
