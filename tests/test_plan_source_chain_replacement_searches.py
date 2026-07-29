import csv
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_planner():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "plan_source_chain_replacement_searches.py"
    spec = importlib.util.spec_from_file_location("plan_source_chain_replacement_searches", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_replacement_tasks_prioritize_frontend_gap_ayr_and_routes():
    planner = load_planner()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        scores = tmp_path / "scores.csv"
        with scores.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["record_id", "existing_source_name", "existing_source_url", "machine_bucket"])
            writer.writeheader()
            writer.writerow({"record_id": "1", "existing_source_name": "Australian Yowie Research", "existing_source_url": "https://yowiehunters.com.au/test-ghost", "machine_bucket": "RED_DISCOVERY_ONLY_LEAKAGE"})
        cmap = tmp_path / "map.csv"
        with cmap.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["record_id", "title", "year", "state", "source_stated_place_text"])
            writer.writeheader()
            writer.writerow({"record_id": "1", "title": "Ghost at Perth", "year": "1940", "state": "WA", "source_stated_place_text": "Perth"})
        tasks = planner.plan_tasks(scores, ROOT / "config" / "source_registry.yml", cmap, tmp_path / "out.csv", tmp_path / "report.md", 10)
        assert tasks
        task = tasks[0]
        assert "frontend_public_map_row" in task["priority_reason"]
        assert "1926_1976" in task["priority_reason"]
        assert "trove_newspapers_gazettes" in task["suggested_route_ids_json"]
        assert "nla_catalogue" in task["suggested_route_ids_json"]
