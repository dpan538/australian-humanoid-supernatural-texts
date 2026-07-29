import importlib.util
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "build_noauth_open_probe_plan.py"
    spec = importlib.util.spec_from_file_location("build_noauth_open_probe_plan", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def matrix():
    return {
        "time_bands": [
            {"id": "1955_1964", "start_year": 1955, "end_year": 1964},
            {"id": "1940_1954", "start_year": 1940, "end_year": 1954},
        ],
        "states": {"WA": {"locality_terms": ["Perth"]}, "NSW": {"locality_terms": ["Sydney"]}},
        "term_families": {
            "humanoid_hairy": {"ethics_risk": "medium", "terms": ["yowie"]},
            "named_local_legend": {"ethics_risk": "medium_high", "terms": ["bunyip"]},
        },
    }


def test_api_login_paywall_and_trove_api_routes_are_excluded_from_auto():
    mod = load_module()
    seeds = [
        {"route_id": "trove_api", "source_id": "trove_newspapers_gazettes", "source_name": "Trove API", "state": "WA", "states": ["WA"], "source_tier": "A", "route_family": "trove_newspaper_metadata", "collection_mode": "semi_automated_metadata", "evidence_or_discovery": "evidence_possible", "official_url": "https://api.trove.nla.gov.au/", "api_key_required": True, "login_required": False, "paywall_required": False, "noauth_allowed": True, "max_pages_per_run": 5},
        {"route_id": "login", "source_id": "login", "source_name": "Login", "state": "WA", "states": ["WA"], "source_tier": "A", "route_family": "state_library_catalogue", "collection_mode": "semi_automated_metadata", "evidence_or_discovery": "evidence_possible", "official_url": "https://example.test/", "api_key_required": False, "login_required": True, "paywall_required": False, "noauth_allowed": True, "max_pages_per_run": 5},
        {"route_id": "safe", "source_id": "safe", "source_name": "Safe WA", "state": "WA", "states": ["WA"], "source_tier": "A", "route_family": "state_library_catalogue", "collection_mode": "semi_automated_metadata", "evidence_or_discovery": "evidence_possible", "official_url": "https://example.test/", "search_url_template": "https://example.test/?q={query}", "api_key_required": False, "login_required": False, "paywall_required": False, "noauth_allowed": True, "max_pages_per_run": 10},
    ]
    auto, manual, excluded = mod.build_rows(seeds, matrix(), 50, 50)
    assert {row["route_id"] for row in auto} == {"safe"}
    assert excluded["api_key_required"] == 1
    assert excluded["login_required"] == 1
    assert all(row["route_id"] != "trove_api" for row in auto)


def test_manual_sensitive_goes_to_manual_and_late_wa_scores_high():
    mod = load_module()
    seeds = [
        {"route_id": "safe", "source_id": "safe", "source_name": "Safe WA", "state": "WA", "states": ["WA"], "source_tier": "A", "route_family": "state_library_catalogue", "collection_mode": "semi_automated_metadata", "evidence_or_discovery": "evidence_possible", "official_url": "https://example.test/", "search_url_template": "https://example.test/?q={query}", "api_key_required": False, "login_required": False, "paywall_required": False, "noauth_allowed": True, "max_pages_per_run": 10},
        {"route_id": "sensitive", "source_id": "sensitive", "source_name": "Sensitive", "state": "WA", "states": ["WA"], "source_tier": "A", "route_family": "indigenous_collection_catalogue", "collection_mode": "manual_sensitive_review", "evidence_or_discovery": "manual_only_sensitive", "official_url": "https://example.test/", "api_key_required": False, "login_required": False, "paywall_required": False, "noauth_allowed": True, "max_pages_per_run": 10},
    ]
    auto, manual, _excluded = mod.build_rows(seeds, matrix(), 50, 50)
    assert auto
    assert max(int(row["sample_weight"]) for row in auto) >= 160
    assert any(row["route_id"] == "sensitive" and row["reason_manual"] == "manual_sensitive_review" for row in manual)
