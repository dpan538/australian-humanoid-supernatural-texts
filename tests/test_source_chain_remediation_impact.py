import csv
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_impact():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "score_source_chain_remediation_impact.py"
    spec = importlib.util.spec_from_file_location("score_source_chain_remediation_impact", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_impact_estimates_replacement_and_additions():
    impact = load_impact()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        audit = tmp_path / "audit.csv"
        with audit.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["source_family", "row_count", "rows_1926_1976"])
            writer.writeheader()
            writer.writerow({"source_family": "AYR_FAMILY", "row_count": "60", "rows_1926_1976": "30"})
            writer.writerow({"source_family": "OTHER", "row_count": "40", "rows_1926_1976": "20"})
        tasks = tmp_path / "tasks.csv"
        with tasks.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["task_id"])
            writer.writeheader()
            for i in range(75):
                writer.writerow({"task_id": str(i)})
        rows = impact.estimate(audit, tasks, tmp_path / "out.csv", tmp_path / "report.md")
        assert rows[0]["current_ayr_frontend_share"] == 60.0
        assert rows[0]["tasks_assumed_successful"] == 50
        assert int(rows[0]["new_non_ayr_records_needed_for_5pt_drop"]) > 0
