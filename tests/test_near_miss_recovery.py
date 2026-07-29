import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("near_miss_recovery_mod", scripts / "recover_gap_near_misses.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_term_no_date_and_date_no_term_categories_route_to_followup_lanes():
    mod = load()
    assert mod.recovery_category({"target_gap_reason": "missing_explicit_target_temporal_evidence"}) == "TERM_NO_DATE"
    assert mod.recovery_category({"target_gap_reason": "missing_controlled_term"}) == "DATE_NO_TERM"


def test_pdf_and_catalogue_near_misses_are_not_promoted_by_category_alone():
    mod = load()
    assert mod.recovery_category({"url": "https://example.test/issue.pdf"}) == "PDF_LINK_NOT_PROCESSED"
    assert mod.recovery_category({"gate_reasons_json": "possible catalogue result"}) == "POSSIBLE_CATALOGUE_RESULT"
