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
    path = scripts / "migrate_collection_expansion_v2.py"
    spec = importlib.util.spec_from_file_location("migrate_collection_expansion_v2", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_collection_expansion_migration_is_idempotent():
    migration = load_migration()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        migration.migrate(db_path)
        migration.migrate(db_path)
        conn = sqlite3.connect(db_path)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        finally:
            conn.close()
    assert {"collection_routes", "source_chains", "collection_candidates", "release_gate_results"}.issubset(tables)
    assert "idx_collection_candidates_run_id" in indexes
