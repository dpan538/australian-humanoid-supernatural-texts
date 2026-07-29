import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_common():
    path = ROOT / "scripts" / "collection_expansion_common.py"
    spec = importlib.util.spec_from_file_location("collection_expansion_common", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_valid_registry_loads():
    common = load_common()
    rows = common.load_registry(ROOT / "config" / "source_registry.yml")
    assert rows
    assert {row["source_id"] for row in rows} >= {"trove_newspapers_gazettes", "act_heritage_library"}


def test_missing_required_fields_raises_value_error():
    common = load_common()
    item = {
        "source_id": "bad",
        "source_name": "Bad",
        "source_tier": "A",
        "evidence_or_discovery": "evidence_possible",
    }
    try:
        common.validate_registry_item(item)
    except ValueError:
        return
    raise AssertionError("missing required fields should raise ValueError")


def test_source_tier_mapping_is_accepted():
    common = load_common()
    mode_by_tier = {
        "A": "evidence_possible",
        "B": "evidence_possible",
        "C": "evidence_possible",
        "D": "evidence_only_if_original_source_identified",
        "E": "discovery_only",
    }
    for tier, mode in mode_by_tier.items():
        common.validate_registry_item(
            {
                "source_id": f"tier_{tier}",
                "source_name": "Tier",
                "institution": "Institution",
                "route_family": "test",
                "source_tier": tier,
                "evidence_or_discovery": mode,
                "scope": "test",
                "states": ["WA"],
                "access_method": "metadata",
                "allowed_content_mode": "metadata_only",
            }
        )


def test_discovery_only_tier_cannot_be_evidence_possible():
    common = load_common()
    try:
        common.validate_registry_item(
            {
                "source_id": "bad_evidence",
                "source_name": "Bad Evidence",
                "institution": "Institution",
                "route_family": "test",
                "source_tier": "E",
                "evidence_or_discovery": "evidence_possible",
                "scope": "test",
                "states": ["WA"],
                "access_method": "metadata",
                "allowed_content_mode": "metadata_only",
            }
        )
    except ValueError:
        return
    raise AssertionError("tier E evidence_possible should raise ValueError")
