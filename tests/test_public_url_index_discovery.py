import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("public_index_mod", scripts / "discover_targets_via_public_url_indexes.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_trusted_domain_url_pattern_classification_scores_target_signals():
    mod = load()
    row = mod.classify_url("https://history.example.org/newsletter/ghost-1968.pdf", {"route_id": "r", "source_tier": "B", "route_family": "local_history_serial", "state": "WA"}, "WAYBACK_CDX", live=False)
    assert row["live_or_archived"] == "archived_only"
    assert row["next_action"] == "ACCESS_ARCHIVE_CANDIDATE_REQUIRES_DECOMPOSITION"
    assert row["likely_pdf"] == 1
    assert row["target_priority_score"] > 0


def test_google_bing_trove_index_sources_are_rejected():
    mod = load()
    assert not mod.safe_index_source("https://www.google.com/search?q=site:x")
    assert not mod.safe_index_source("https://api.bing.microsoft.com/v7.0/search")
    assert not mod.safe_index_source("https://api.trove.nla.gov.au/v3/result")
    assert mod.safe_index_source("https://web.archive.org/cdx?url=example.org/*ghost*")
