import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_scores():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "score_probe_candidates.py"
    spec = importlib.util.spec_from_file_location("score_probe_candidates", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def candidate(**overrides):
    row = {
        "candidate_id": "c1",
        "source_tier": "A",
        "evidence_or_discovery": "evidence_possible",
        "target_state": "WA",
        "time_band": "1940_1954",
        "term_family": "yowie",
        "title": "Yowie report near Perth",
        "snippet": "A local yowie report.",
        "publication": "Test Paper",
        "date_published": "1941-01-01",
        "url": "https://example.test",
        "duplicate_key": "dup1",
    }
    row.update(overrides)
    return row


def test_priority_candidate_scores_priority_review():
    scores = load_scores()
    result = scores.score_candidate(candidate(), set())
    assert result["machine_bucket"] == "PRIORITY_REVIEW"


def test_discovery_only_candidate_not_auto_evidence():
    scores = load_scores()
    result = scores.score_candidate(candidate(source_tier="E", evidence_or_discovery="discovery_only"), set())
    assert "discovery_only_not_auto_evidence" in result["hard_fail_reasons"]


def test_duplicate_candidate_is_excluded():
    scores = load_scores()
    seen = {"dup1"}
    result = scores.score_candidate(candidate(), seen)
    assert result["machine_bucket"] == "EXCLUDE_DUPLICATE"


def test_missing_date_is_amber():
    scores = load_scores()
    result = scores.score_candidate(candidate(date_published="", time_band="1940_1954"), set())
    assert result["machine_bucket"] == "AMBER_MISSING_DATE"
