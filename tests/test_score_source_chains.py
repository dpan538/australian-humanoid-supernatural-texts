import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_scores():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "score_source_chains.py"
    spec = importlib.util.spec_from_file_location("score_source_chains", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_internet_archive_needs_original_source_review():
    scores = load_scores()
    result = scores.score_source_chain(
        {
            "existing_source_name": "Internet Archive",
            "existing_source_url": "https://archive.org/details/test",
            "inferred_access_source_name": "Internet Archive",
            "inferred_evidence_source_tier": "D",
        }
    )
    assert result["machine_bucket"] == "AMBER_D_NEEDS_ORIGINAL"


def test_ayr_discovery_only_is_red_leakage():
    scores = load_scores()
    result = scores.score_source_chain(
        {
            "existing_source_name": "Australian Yowie Research",
            "existing_source_url": "https://www.yowiehunters.com.au/",
            "inferred_discovery_source_name": "Australian Yowie Research",
            "inferred_evidence_source_tier": "E",
        }
    )
    assert result["machine_bucket"] == "RED_DISCOVERY_ONLY_LEAKAGE"


def test_state_library_evidence_scores_green():
    scores = load_scores()
    result = scores.score_source_chain(
        {
            "existing_source_name": "State Library of Western Australia",
            "existing_source_url": "https://slwa.wa.gov.au/item",
            "inferred_evidence_source_name": "State Library of Western Australia catalogue",
            "inferred_evidence_source_tier": "A",
            "date_published": "1941",
        }
    )
    assert result["machine_bucket"] == "GREEN_EVIDENCE_OK"
