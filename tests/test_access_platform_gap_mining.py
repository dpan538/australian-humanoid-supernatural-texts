import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("access_platform_mod", scripts / "mine_noauth_access_platforms_for_gap.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_internet_archive_candidate_is_access_not_evidence_by_default():
    mod = load()
    row = mod.classify_access({"title": "Ghost story 1968", "snippet": "A haunted local history item", "date_text": "1968", "rights_status": "unknown", "url": "https://archive.org/details/x"}, "run")
    assert row["current_status"] == "TARGET_GAP_ACCESS_CANDIDATE"
    assert row["source_chain_status"] == "requires_original_source_decomposition"


def test_public_domain_candidate_requires_decomposition_before_evidence_use():
    mod = load()
    row = mod.classify_access({"title": "Ghost story 1930", "snippet": "public domain haunted pamphlet", "date_text": "1930", "rights_status": "public domain", "url": "https://archive.org/details/y"}, "run")
    assert row["current_status"] == "ORIGINAL_SOURCE_DECOMPOSED_CANDIDATE"
    assert row["next_action"] == "decompose_original_source_before_evidence_use"
