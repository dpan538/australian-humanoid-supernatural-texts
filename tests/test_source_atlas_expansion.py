import importlib.util
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("atlas_expansion_mod", scripts / "expand_routes_from_source_atlas.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_source_atlas_adds_safe_noauth_and_excludes_api_sensitive_authority():
    mod = load()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        atlas = root / "atlas.md"
        registry = root / "registry.yml"
        seeds = root / "seeds.yml"
        out = root / "expanded.yml"
        report = root / "report.md"
        atlas.write_text("`safe_local` `trove_api` `sensitive_route` `authority_route`", encoding="utf-8")
        registry.write_text(
            yaml.safe_dump(
                [
                    {"source_id": "safe_local", "source_name": "Safe Local", "source_tier": "B", "route_family": "local_history_serial", "states": ["WA"], "official_url": "https://safe.test", "evidence_or_discovery": "evidence_possible"},
                    {"source_id": "trove_api", "source_name": "Trove", "source_tier": "A", "route_family": "state_library_catalogue", "states": ["WA"], "official_url": "https://api.trove.nla.gov.au/v3/result", "evidence_or_discovery": "evidence_possible"},
                    {"source_id": "sensitive_route", "source_name": "Sensitive", "source_tier": "A", "route_family": "local_history_serial", "states": ["WA"], "official_url": "https://sensitive.test", "evidence_or_discovery": "manual_only_sensitive"},
                    {"source_id": "authority_route", "source_name": "Authority", "source_tier": "A", "route_family": "gazetteer", "states": ["WA"], "official_url": "https://authority.test", "evidence_or_discovery": "discovery_only"},
                ],
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        seeds.write_text("[]\n", encoding="utf-8")
        result = mod.expand(atlas, registry, seeds, out, report)
        expanded = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert result["added"] == 1
        assert expanded[0]["route_id"] == "safe_local"
        text = report.read_text(encoding="utf-8")
        assert "api_or_trove_api" in text
        assert "manual_sensitive" in text
        assert "discovery_or_authority_only" in text
