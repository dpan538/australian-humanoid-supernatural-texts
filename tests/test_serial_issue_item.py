import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("serial_issue_test", scripts / "lib/autoharvest_gap.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CONFIG = {"temporal_gate": {"min_date_confidence": 0.7}, "term_gate": {"controlled_terms": ["ghost", "haunted hotel"]}}


def base(**extra):
    row = {
        "title": "Historical Society Newsletter June 1968",
        "snippet": "A ghost story appears in this issue.",
        "url": "https://example.test/newsletter/june-1968.pdf",
        "date_published": "June 1968",
        "source_tier": "A",
        "target_state": "SA",
        "evidence_source_name": "Historical Society",
        "evidence_source_url": "https://example.test/newsletter/june-1968.pdf",
        "duplicate_status": "unique",
        "ethics_status": "not_sensitive",
        "evidence_or_discovery": "evidence_possible",
    }
    row.update(extra)
    return row


def test_newsletter_issue_with_date_and_ghost_qualifies():
    g = load()
    decision = g.classify_gap_candidate(base(), {}, CONFIG, page_text="newsletter issue ghost")
    assert decision.target_gap_eligible
    assert decision.item_format in {"PDF_ISSUE", "SERIAL_ISSUE_ITEM"}


def test_issue_date_without_term_fails_and_term_without_date_near_misses():
    g = load()
    no_term = g.classify_gap_candidate(base(snippet="Local history notes.", url="https://example.test/newsletter/june-1968.pdf"), {}, CONFIG, page_text="newsletter issue")
    no_date = g.classify_gap_candidate(base(title="Historical Society Newsletter", date_published="", url="https://example.test/newsletter/june.pdf"), {}, CONFIG, page_text="newsletter issue ghost")
    assert not no_term.target_gap_eligible
    assert "missing_controlled_term" in no_term.reason
    assert not no_date.target_gap_eligible
    assert no_date.auxiliary_status == "UNDATED_AUXILIARY"
