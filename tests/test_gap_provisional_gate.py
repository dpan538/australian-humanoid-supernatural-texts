import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("gap_gate_test", scripts / "lib/autoharvest_gap.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CONFIG = {"temporal_gate": {"min_date_confidence": 0.7}, "term_gate": {"controlled_terms": ["ghost", "haunted", "yowie"]}}


def candidate(**extra):
    row = {
        "title": "1955 ghost catalogue record",
        "snippet": "A ghost was reported in 1955 near Kalgoorlie.",
        "url": "https://example.test/catalogue/item/1955-ghost",
        "date_published": "1955",
        "source_tier": "A",
        "target_state": "WA",
        "evidence_source_name": "State Library",
        "evidence_source_url": "https://example.test/catalogue/item/1955-ghost",
        "duplicate_status": "unique",
        "ethics_status": "not_sensitive",
        "evidence_or_discovery": "evidence_possible",
    }
    row.update(extra)
    return row


def test_target_gap_effective_requires_temporal_term_item_and_tier():
    g = load()
    decision = g.classify_gap_candidate(candidate(), {"state": "WA"}, CONFIG, page_text="Date 1955 ghost catalogue item")
    assert decision.target_gap_eligible
    assert decision.reason == "TARGET_GAP_EFFECTIVE"


def test_auxiliary_and_reject_buckets():
    g = load()
    undated = g.classify_gap_candidate(
        candidate(title="Ghost catalogue record", url="https://example.test/catalogue/item/ghost", date_published="", snippet="A ghost story near Kalgoorlie."),
        {},
        CONFIG,
        page_text="ghost catalogue item record",
    )
    no_term = g.classify_gap_candidate(
        candidate(
            title="1955 local history",
            snippet="A town article in 1955.",
            url="https://example.test/catalogue/item/local-history-1955",
            evidence_source_url="https://example.test/catalogue/item/local-history-1955",
        ),
        {},
        CONFIG,
        page_text="Date 1955 catalogue item",
    )
    discovery = g.classify_gap_candidate(candidate(evidence_or_discovery="discovery_only"), {}, CONFIG, page_text="Date 1955 ghost item")
    sensitive = g.classify_gap_candidate(candidate(ethics_status="manual_only"), {}, CONFIG, page_text="Date 1955 ghost item")
    tourism = g.classify_gap_candidate(candidate(snippet="ghost tour tickets booking 1955"), {}, {"noise_terms": {"tourism": ["tickets", "booking"]}, **CONFIG}, page_text="Date 1955 ghost item")
    duplicate = g.classify_gap_candidate(candidate(duplicate_status="duplicate"), {}, CONFIG, page_text="Date 1955 ghost item")
    assert undated.auxiliary_status == "UNDATED_AUXILIARY"
    assert no_term.auxiliary_status in {"GENERAL_SAFE_PROVISIONAL", "UNDATED_AUXILIARY"}
    assert discovery.auxiliary_status == "REJECTED_OR_HELD"
    assert sensitive.auxiliary_status == "REJECTED_OR_HELD"
    assert tourism.auxiliary_status == "REJECTED_OR_HELD"
    assert duplicate.auxiliary_status == "REJECTED_OR_HELD"
