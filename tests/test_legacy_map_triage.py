import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_triage():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "triage_existing_map_flags.py"
    spec = importlib.util.spec_from_file_location("triage_existing_map_flags", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_row():
    return {
        "source_stated_place_text": "Kalgoorlie",
        "location_role": "alleged_event_location",
        "jurisdiction_state": "WA",
        "lat": -30.75,
        "lng": 121.47,
        "coordinate_precision": "locality",
        "review_status": "reviewed",
        "ethics_flags_json": "{}",
        "display_decision": "metadata_only",
    }


def test_missing_source_stated_place_text_needs_review():
    triage = load_triage()
    row = valid_row()
    row["source_stated_place_text"] = ""
    action, reason = triage.classify_map_flag(row)
    assert action == "needs_place_evidence_review"
    assert "missing_source_stated_place_text" in reason


def test_publication_place_demotes_to_unmapped():
    triage = load_triage()
    row = valid_row()
    row["location_role"] = "publication_place"
    action, reason = triage.classify_map_flag(row)
    assert action == "demote_to_unmapped"
    assert "invalid_location_role:publication_place" in reason


def test_sensitive_without_display_decision_requires_manual_sensitive_review():
    triage = load_triage()
    row = valid_row()
    row["display_decision"] = ""
    row["ethics_flags_json"] = '{"ethics_review_status":"sensitive"}'
    action, reason = triage.classify_map_flag(row)
    assert action == "manual_sensitive_review"
    assert "sensitive_without_display_decision" in reason


def test_valid_row_keeps_public_map_flag():
    triage = load_triage()
    action, reason = triage.classify_map_flag(valid_row())
    assert action == "keep_public_map_flag"
    assert reason == ""
