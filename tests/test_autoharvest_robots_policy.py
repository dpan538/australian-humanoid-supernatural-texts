import importlib.util
import requests
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_engine():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("autoharvest_engine_robots", scripts / "lib" / "autoharvest_engine.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_robots_unknown_or_disallowed_fails_closed():
    eng = load_engine()
    original = eng.allowed_by_robots
    try:
        eng.allowed_by_robots = lambda *_args, **_kwargs: False
        result = eng.fetch_page_safe("https://example.test/page", {"route_id": "r"}, eng.HarvestConfig({"safety": {}}))
        assert result.status == "robots_blocked"
    finally:
        eng.allowed_by_robots = original


def test_429_and_403_trigger_backoff_pauses():
    eng = load_engine()
    original_allowed = eng.allowed_by_robots
    original_fetch = eng.fetch_html_safe
    class Response:
        def __init__(self, code):
            self.status_code = code
    try:
        eng.allowed_by_robots = lambda *_args, **_kwargs: True
        def raise_429(*_args, **_kwargs):
            exc = requests.HTTPError("too many")
            exc.response = Response(429)
            raise exc
        eng.fetch_html_safe = raise_429
        result = eng.fetch_page_safe("https://example.test/page", {"route_id": "r"}, eng.HarvestConfig({"safety": {"backoff_on_429_seconds": 900, "backoff_on_403_seconds": 86400}}))
        assert result.status == "backoff"
        assert result.backoff_seconds == 900
        def raise_403(*_args, **_kwargs):
            exc = requests.HTTPError("forbidden")
            exc.response = Response(403)
            raise exc
        eng.fetch_html_safe = raise_403
        result = eng.fetch_page_safe("https://example.test/page", {"route_id": "r"}, eng.HarvestConfig({"safety": {"backoff_on_429_seconds": 900, "backoff_on_403_seconds": 86400}}))
        assert result.status == "paused"
        assert result.backoff_seconds == 86400
    finally:
        eng.allowed_by_robots = original_allowed
        eng.fetch_html_safe = original_fetch
