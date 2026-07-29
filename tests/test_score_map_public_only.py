import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_scores():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "score_map_evidence.py"
    spec = importlib.util.spec_from_file_location("score_map_evidence", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_row():
    return {
        "record_id": "r1",
        "source_stated_place_text": "Kalgoorlie",
        "location_role": "alleged_event_location",
        "jurisdiction_state": "WA",
        "current_state": "WA",
        "current_lat": -30.75,
        "current_lng": 121.47,
        "coordinate_precision": "locality",
        "review_status": "reviewed",
        "source_url": "https://example.test/source",
        "partition_label": "FRONTEND_PUBLIC_MAP",
    }


def test_non_public_internal_row_is_ignored_not_red():
    scores = load_scores()
    row = valid_row()
    row["partition_label"] = "INTERNAL_LOCATION_ROW"
    result = scores.score_map_row(row)
    assert result["machine_bucket"] == "NONPUBLIC_IGNORE"


def test_frontend_public_invalid_role_is_public_red_demote():
    scores = load_scores()
    row = valid_row()
    row["location_role"] = "publication_location"
    result = scores.score_map_row(row)
    assert result["machine_bucket"] == "RED_PUBLIC_DEMOTE_ELIGIBLE"


def test_frontend_public_valid_row_is_green():
    scores = load_scores()
    result = scores.score_map_row(valid_row())
    assert result["machine_bucket"] == "GREEN_KEEP_PUBLIC"


def test_frontend_public_missing_place_is_amber_place_review():
    scores = load_scores()
    row = valid_row()
    row["source_stated_place_text"] = ""
    result = scores.score_map_row(row)
    assert result["machine_bucket"] == "AMBER_PUBLIC_PLACE_REVIEW"
