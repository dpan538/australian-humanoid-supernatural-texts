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


def test_stable_candidate_id_is_deterministic():
    common = load_common()
    first = common.stable_candidate_id("src", "id", "https://example.test", "Title", "1940", "ghost")
    second = common.stable_candidate_id("src", "id", "https://example.test", "Title", "1940", "ghost")
    assert first == second
    assert first.startswith("cand_")


def test_duplicate_key_normalizes_whitespace_and_case():
    common = load_common()
    first = common.duplicate_key(" Haunted   Hotel ", "Paper", "1940", "https://example.test/a", None)
    second = common.duplicate_key("haunted hotel", " paper ", "1940", "https://example.test/a", None)
    assert first == second
