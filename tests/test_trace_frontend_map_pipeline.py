import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_trace():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "trace_frontend_map_pipeline.py"
    spec = importlib.util.spec_from_file_location("trace_frontend_map_pipeline", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_trace_extracts_frontend_map_count_and_manifest_fields():
    trace = load_trace()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_dir = root / "public" / "data"
        data_dir.mkdir(parents=True)
        rows = [{"record_id": i, "title": f"Record {i}", "latitude": -30.0, "longitude": 120.0 + i, "url": "https://example.test"} for i in range(1593)]
        (data_dir / "frontend-data.json").write_text(json.dumps({"records": [], "map_points": rows, "map_flags": []}), encoding="utf-8")
        scripts = root / "scripts"
        scripts.mkdir()
        (scripts / "export_frontend_json.py").write_text("map_points = []\nFRONTEND_DATA_PATH='public/data/frontend-data.json'\n", encoding="utf-8")
        db = root / "test.sqlite"
        sqlite3.connect(db).close()
        manifest = trace.trace(root, db, root / "frontend", root / "data" / "exports" / "v2", root / "out")
        assert manifest["frontend_map_count"] == 1593
        assert manifest["frontend_map_file"] == "public/data/frontend-data.json"
        assert manifest["canonical_join_key_strategy"] == "record_id+coordinate_pair"
        assert (root / "out" / "frontend_map_id_candidates.csv").exists()
