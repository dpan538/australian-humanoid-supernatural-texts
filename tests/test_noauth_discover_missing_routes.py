import csv
import importlib.util
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "noauth_discover_missing_routes.py"
    spec = importlib.util.spec_from_file_location("noauth_discover_missing_routes", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def seed_file(path: Path):
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "route_id": "seed",
                    "source_id": "seed",
                    "source_name": "Seed",
                    "official_url": "https://example.test/",
                    "state": "WA",
                    "route_family": "local_history_directory",
                    "source_tier": "B",
                    "api_key_required": False,
                    "login_required": False,
                    "paywall_required": False,
                }
            ]
        ),
        encoding="utf-8",
    )


def test_trusted_directory_page_yields_review_candidate_routes():
    mod = load_module()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        seeds = base / "seeds.yml"
        out = base / "routes.csv"
        report = base / "report.md"
        seed_file(seeds)
        original_allowed = mod.allowed_by_robots
        original_fetch = mod.fetch_html_safe
        try:
            mod.allowed_by_robots = lambda *_args, **_kwargs: True
            mod.fetch_html_safe = lambda *_args, **_kwargs: "<a href='https://example.test/archive'>Local archives</a><a href='https://shop.example.com'>Shop</a>"
            summary = mod.discover(seeds, out, report, 10, execute=True)
        finally:
            mod.allowed_by_robots = original_allowed
            mod.fetch_html_safe = original_fetch
        rows = list(csv.DictReader(out.open(encoding="utf-8")))
        assert summary["rows"] == 1
        assert rows[0]["recommended_action"] == "REVIEW_ROUTE_CANDIDATE"
        assert "Source registry mutations: `none`" in report.read_text(encoding="utf-8")


def test_dry_run_outputs_seed_inventory_only():
    mod = load_module()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        seeds = base / "seeds.yml"
        out = base / "routes.csv"
        report = base / "report.md"
        seed_file(seeds)
        summary = mod.discover(seeds, out, report, 10, execute=False)
        assert summary["rows"] == 1
        assert list(csv.DictReader(out.open(encoding="utf-8")))[0]["reason_discovered"] == "dry_run_seed_inventory"
