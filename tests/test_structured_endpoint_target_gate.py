import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("structured_endpoints_mod_gate", scripts / "lib" / "structured_endpoints.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def config():
    return {"target_queries": {"controlled_terms": ["ghost"]}, "temporal_gate": {"min_date_confidence": 0.7}}


def test_abc_item_with_term_and_date_can_be_target_effective():
    mod = load()
    record = mod.EndpointRecord("https://library.example/item/1", "1", "Ghost at Albany station", "Published 1935 with local evidence", date_text="1935", source_tier="A")
    scored = mod.score_endpoint_record(record, {"endpoint_id": "ep1", "route_id": "r1", "source_name": "State Library", "source_tier": "A", "endpoint_type": "OAI_PMH", "state": "WA"}, {"query_text": "ghost", "controlled_term": "ghost"}, config(), "run")
    assert scored["decision"].target_gap_eligible is True
    assert scored["status"] == "TARGET_GAP_EFFECTIVE"


def test_d_class_access_platform_requires_original_source_decomposition():
    mod = load()
    record = mod.EndpointRecord("https://archive.org/details/x", "x", "Ghost story 1935", "A haunted item", date_text="1935", source_tier="D")
    scored = mod.score_endpoint_record(record, {"endpoint_id": "ep2", "route_id": "r2", "source_name": "Internet Archive", "source_tier": "D", "endpoint_type": "INTERNET_ARCHIVE_METADATA"}, {"query_text": "ghost", "controlled_term": "ghost"}, config(), "run")
    assert scored["decision"].target_gap_eligible is False
    assert "d_class_requires_original_source_decomposition" in scored["decision"].reasons
