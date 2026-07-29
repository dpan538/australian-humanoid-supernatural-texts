import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_engine_and_migration():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    def load(name, rel):
        spec = importlib.util.spec_from_file_location(name, scripts / rel)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    return load("autoharvest_engine_api", Path("lib/autoharvest_engine.py")), load("migrate_autoharvest_v1_api", Path("migrate_autoharvest_v1.py"))


def test_trove_api_key_is_ignored_and_api_urls_rejected():
    eng, _mig = load_engine_and_migration()
    old = os.environ.get("TROVE_API_KEY")
    os.environ["TROVE_API_KEY"] = "secret"
    try:
        ok, reasons = eng.classify_route_safety(
            {"official_url": "https://api.trove.nla.gov.au/v3/result", "source_tier": "A", "evidence_or_discovery": "evidence_possible"},
            eng.HarvestConfig({"safety": {}}),
        )
    finally:
        if old is None:
            os.environ.pop("TROVE_API_KEY", None)
        else:
            os.environ["TROVE_API_KEY"] = old
    assert not ok
    assert "api_url_rejected" in reasons
    assert "trove_api_rejected" in reasons
    assert not eng.classify_route_safety({"official_url": "https://www.googleapis.com/customsearch/v1"}, eng.HarvestConfig({}))[0]
    assert not eng.classify_route_safety({"official_url": "https://api.bing.microsoft.com/v7.0/search"}, eng.HarvestConfig({}))[0]


def test_api_key_route_does_not_enter_frontier():
    eng, mig = load_engine_and_migration()
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            summary = eng.seed_frontier(
                conn,
                "run",
                [
                    {"route_id": "api", "source_id": "api", "official_url": "https://example.test/", "api_key_required": True, "evidence_or_discovery": "evidence_possible"},
                    {"route_id": "safe", "source_id": "safe", "official_url": "https://example.test/", "source_tier": "A", "route_family": "local_history_serial", "state": "WA", "evidence_or_discovery": "evidence_possible"},
                ],
                eng.HarvestConfig({"priority": {"states": {"WA": 60}, "route_families": {"local_history_serial": 55}}}),
            )
            queued = conn.execute("SELECT COUNT(*) FROM harvest_frontier").fetchone()[0]
        assert summary["rejected"] == 1
        assert queued == 1
