import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_engine():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "lib" / "autoharvest_engine.py"
    spec = importlib.util.spec_from_file_location("autoharvest_engine", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def config():
    return {
        "candidate_gates": {"min_candidate_score_for_provisional": 80},
        "noise_terms": {
            "tourism": ["ghost tour", "tickets"],
            "context_noise": ["fiction", "theatre"],
        },
    }


def route(**overrides):
    row = {
        "source_tier": "A",
        "state": "WA",
        "route_family": "local_history_serial",
        "evidence_or_discovery": "evidence_possible",
        "collection_mode": "static_html_metadata",
        "source_name": "WA Local History",
    }
    row.update(overrides)
    return row


def candidate(**overrides):
    row = {
        "url": "https://example.test/record",
        "title": "Perth ghost local history 1960",
        "snippet": "Perth ghost record in local history collection",
        "source_tier": "A",
        "target_state": "WA",
        "inferred_year": 1960,
        "time_band": "1955_1964",
        "source_stated_place_text": "Perth",
        "evidence_source_name": "WA Local History",
        "evidence_source_url": "https://example.test/record",
        "access_source_url": "https://example.test/",
        "duplicate_status": "unique",
        "ethics_status": "not_sensitive",
        "rights_status": "metadata_only",
        "evidence_or_discovery": "evidence_possible",
    }
    row.update(overrides)
    return row


def test_tier_a_local_history_candidate_passes_gate():
    eng = load_engine()
    cand = candidate()
    score, reasons = eng.score_candidate(cand, route(), config())
    ok, fail = eng.provisional_gate(cand, score, reasons, config())
    assert score >= 80
    assert ok
    assert fail == []


def test_discovery_sensitive_tourism_duplicate_and_missing_evidence_fail():
    eng = load_engine()
    cases = [
        (candidate(evidence_or_discovery="discovery_only"), route(evidence_or_discovery="discovery_only"), "discovery_or_sensitive_route"),
        (candidate(ethics_status="sensitive"), route(), "sensitive_or_restricted"),
        (candidate(title="Perth ghost tour tickets 1960"), route(), "context_noise"),
        (candidate(duplicate_status="duplicate"), route(), "duplicate"),
        (candidate(evidence_source_url=""), route(), "missing_evidence_source_url"),
    ]
    for cand, rt, expected in cases:
        score, reasons = eng.score_candidate(cand, rt, config())
        ok, fail = eng.provisional_gate(cand, score, reasons, config())
        assert not ok
        assert expected in fail
