import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "noauth_score_open_candidates.py"
    spec = importlib.util.spec_from_file_location("noauth_score_open_candidates", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def row(**overrides):
    base = {
        "source_tier": "A",
        "target_state": "WA",
        "time_band": "1955_1964",
        "route_family": "council_local_studies",
        "term_family": "ghost",
        "target_locality": "Perth",
        "title": "Perth ghost archive 1960",
        "snippet": "Local history collection record for Perth ghost story in 1960",
        "url": "https://library.wa.gov.au/record",
        "date_published": "1960",
        "source_stated_place_text": "Perth",
        "duplicate_status": "unchecked",
    }
    base.update(overrides)
    return base


def test_official_wa_late_local_history_hit_is_priority():
    mod = load_module()
    score, bucket, _reasons = mod.score_row(row())
    assert score >= 80
    assert bucket == "PRIORITY_REVIEW_OPEN_RECORD"


def test_tourism_page_is_excluded():
    mod = load_module()
    _score, bucket, reasons = mod.score_row(row(title="Perth ghost tour tickets 1960"))
    assert bucket == "EXCLUDE_TOURISM_MARKETING"
    assert "tourism_marketing" in reasons


def test_context_noise_missing_date_and_duplicate_buckets():
    mod = load_module()
    assert mod.score_row(row(title="Theatre ghost schedule 1960"))[1] == "EXCLUDE_CONTEXT_NOISE"
    assert mod.score_row(row(date_published="", title="Perth ghost archive"))[1] == "AMBER_NEEDS_DATE"
    assert mod.score_row(row(duplicate_status="duplicate"))[1] == "EXCLUDE_DUPLICATE"
