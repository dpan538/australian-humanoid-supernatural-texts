import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_migration():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "migrate_autoharvest_v1.py"
    spec = importlib.util.spec_from_file_location("migrate_autoharvest_v1", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_autoharvest_migration_is_idempotent_and_indexes_exist():
    mod = load_migration()
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "test.sqlite"
        first = mod.migrate(db)
        second = mod.migrate(db)
        with sqlite3.connect(db) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {
            "harvest_runs",
            "harvest_frontier",
            "harvest_pages",
            "harvest_candidates",
            "provisional_records",
            "harvest_route_stats",
            "harvest_discovered_routes",
            "harvest_milestones",
        }.issubset(tables)
        assert "idx_harvest_frontier_status_priority" in indexes
        assert "idx_provisional_records_duplicate_key" in indexes
        assert len(second["created_tables"]) == 0
