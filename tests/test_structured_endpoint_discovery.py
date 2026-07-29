import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("structured_discovery_mod", scripts / "discover_noauth_structured_endpoints.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    text = "[]"


class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse()


def test_discovery_rejects_api_key_and_finds_wordpress():
    mod = load()
    old_session = mod.requests.Session
    old_robots = mod.allowed_by_robots
    mod.requests.Session = lambda: FakeSession()
    mod.allowed_by_robots = lambda url, ua: True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db = tmp_path / "test.sqlite"
            config = tmp_path / "config.yml"
            seeds = tmp_path / "seeds.yml"
            registry = tmp_path / "registry.yml"
            expanded = tmp_path / "expanded.yml"
            config.write_text(yaml.safe_dump({"endpoint_probe_limits": {"max_domains_per_run": 10, "max_endpoint_tests_per_domain": 12, "timeout_seconds": 1}}), encoding="utf-8")
            rows = [
                {"route_id": "safe", "source_name": "Safe", "source_tier": "B", "official_url": "https://example.org", "route_family": "public_collection", "states": ["WA"]},
                {"route_id": "trove", "source_name": "Trove API", "source_tier": "A", "official_url": "https://api.trove.nla.gov.au/v3/result", "api_key_required": True},
            ]
            seeds.write_text(yaml.safe_dump(rows), encoding="utf-8")
            registry.write_text("[]\n", encoding="utf-8")
            expanded.write_text("[]\n", encoding="utf-8")
            summary = mod.discover(db, config, seeds, registry, expanded, tmp_path / "report.md", True)
            assert summary["endpoints"] >= 1
            with sqlite3.connect(db) as conn:
                urls = [row[0] for row in conn.execute("SELECT endpoint_url FROM noauth_endpoint_inventory")]
            assert any("wp-json" in url for url in urls)
            assert all("api.trove" not in url for url in urls)
    finally:
        mod.requests.Session = old_session
        mod.allowed_by_robots = old_robots
