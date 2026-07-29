import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_robots_failure_returns_false_for_generic_html_route():
    common = load_module("collection_expansion_common")
    common._ROBOT_CACHE.clear()

    class FailingRobotParser:
        def set_url(self, _url):
            pass

        def read(self):
            raise OSError("blocked")

    original = common.RobotFileParser
    try:
        common.RobotFileParser = FailingRobotParser
        assert common.allowed_by_robots("https://example.test/search") is False
    finally:
        common.RobotFileParser = original
        common._ROBOT_CACHE.clear()


def test_manual_only_route_does_not_fetch():
    probe = load_module("probe_public_sources")
    route = {
        "source_id": "manual",
        "evidence_or_discovery": "manual_only_sensitive",
        "access_method": "manual_catalogue_review",
        "allowed_content_mode": "manual_review_only",
    }
    assert probe.should_fetch_route(route, execute=True) is False
