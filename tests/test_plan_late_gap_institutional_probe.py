import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_planner():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "plan_late_gap_institutional_probe.py"
    spec = importlib.util.spec_from_file_location("plan_late_gap_institutional_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_late_gap_plan_scopes_bands_states_and_manual_sensitive():
    planner = load_planner()
    auto, manual = planner.build_rows(ROOT / "config" / "query_matrix_1926_1976.yml", ROOT / "config" / "source_registry.yml", 30, 30)
    assert auto
    assert all(row["time_band"] in {"1955_1964", "1965_1976"} for row in auto)
    assert all(row["target_state"] in {"WA", "SA", "NT", "TAS", "ACT"} for row in auto)
    assert {"WA", "SA", "NT", "TAS", "ACT"}.issubset({row["target_state"] for row in auto})
    assert {"1955_1964", "1965_1976"}.issubset({row["time_band"] for row in auto})
    assert all(row["should_fetch"] == "true" for row in auto)
    assert all(row["should_manual_review"] == "false" for row in auto)
    assert all(row["collection_mode"] == "manual_review_only" for row in manual)
