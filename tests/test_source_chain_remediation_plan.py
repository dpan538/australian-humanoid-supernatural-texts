import csv
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_plan():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "plan_source_chain_remediation.py"
    spec = importlib.util.spec_from_file_location("plan_source_chain_remediation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_source_chain_buckets_go_to_expected_batches():
    planner = load_plan()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        scores = tmp_path / "scores.csv"
        fields = ["record_id", "machine_bucket", "source_name"]
        with scores.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({"record_id": "1", "machine_bucket": "RED_DISCOVERY_ONLY_LEAKAGE", "source_name": "AYR"})
            writer.writerow({"record_id": "2", "machine_bucket": "AMBER_D_NEEDS_ORIGINAL", "source_name": "Internet Archive"})
            writer.writerow({"record_id": "3", "machine_bucket": "AMBER_UNKNOWN_SOURCE", "source_name": "Unknown"})
        counts = planner.plan_remediation(scores, tmp_path / "out")
        assert counts["discovery_only_replacement_batch.csv"] == 1
        assert counts["access_platform_decompose_batch.csv"] == 1
        assert counts["unknown_source_registry_batch.csv"] == 1
        assert (tmp_path / "out" / "remediation_plan.md").exists()
