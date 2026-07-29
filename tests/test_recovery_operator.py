import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_helper():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("gap_recovery_helper", scripts / "lib" / "gap_recovery.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_current_status_with_near_misses_and_pdf_routes_continues_recovery():
    helper = load_helper()
    status = helper.classify_recovery_status(0, 24, 2, search_forms=541)
    assert status == "CONTINUE_RECOVERY"


def test_zero_target_alone_does_not_stop_when_surfaces_remain():
    helper = load_helper()
    assert helper.classify_recovery_status(0, 10, 0, search_forms=0) == "CONTINUE_RECOVERY"
    assert helper.classify_recovery_status(0, 0, 1, search_forms=0) == "CONTINUE_RECOVERY"


def test_repeated_zero_target_with_no_surfaces_is_exhausted():
    helper = load_helper()
    assert helper.classify_recovery_status(0, 2, 0, search_forms=0, index_discoveries=0, route_expansion_candidates=0) == "FAILED_EXHAUSTED"
