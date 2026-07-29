import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_audit():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "audit_collection_balance.py"
    spec = importlib.util.spec_from_file_location("audit_collection_balance", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_targets():
    return {
        "source_caps": {
            "max_single_evidence_source_org_share": 0.20,
            "max_single_access_platform_share": 0.35,
            "max_discovery_only_accepted_records": 0,
        },
        "state_targets": {},
    }


def test_discovery_only_accepted_leakage_produces_fail():
    audit = load_audit()
    gates = audit.evaluate_release_gates({"discovery_only_accepted": 1}, base_targets())
    result = {gate["gate_name"]: gate for gate in gates}
    assert result["discovery_only_accepted_leakage"]["gate_status"] == "FAIL"


def test_missing_source_stated_place_on_mapped_record_produces_fail():
    audit = load_audit()
    gates = audit.evaluate_release_gates({"mapped_missing_required": 1}, base_targets())
    result = {gate["gate_name"]: gate for gate in gates}
    assert result["mapped_records_missing_required_place_evidence"]["gate_status"] == "FAIL"


def test_excessive_source_concentration_produces_warn():
    audit = load_audit()
    gates = audit.evaluate_release_gates({"top_evidence_source_share": 0.5}, base_targets())
    result = {gate["gate_name"]: gate for gate in gates}
    assert result["single_evidence_source_org_share"]["gate_status"] == "WARN"
