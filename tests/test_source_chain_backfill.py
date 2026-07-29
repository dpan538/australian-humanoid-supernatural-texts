import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_backfill():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "backfill_source_chains_existing.py"
    spec = importlib.util.spec_from_file_location("backfill_source_chains_existing", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_internet_archive_source_is_access_platform_tier_d():
    backfill = load_backfill()
    result = backfill.classify_existing_source("Internet Archive", "https://archive.org/details/test")
    assert result["kind"] == "access_platform"
    assert result["source_tier"] == "D"
    assert result["review_status"] == "needs_original_source_review"


def test_ayr_source_is_discovery_only_tier_e():
    backfill = load_backfill()
    result = backfill.classify_existing_source("Australian Yowie Research", "https://www.yowiehunters.com.au/")
    assert result["kind"] == "discovery_only"
    assert result["source_tier"] == "E"
    assert result["review_status"] == "needs_evidence_source_review"


def test_state_library_source_is_public_institution_tier_a():
    backfill = load_backfill()
    result = backfill.classify_existing_source("State Library of Western Australia", "https://slwa.wa.gov.au/")
    assert result["kind"] == "institutional_public_source"
    assert result["source_tier"] == "A"
