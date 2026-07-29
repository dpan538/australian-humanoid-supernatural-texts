import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("structured_endpoints_mod", scripts / "lib" / "structured_endpoints.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeResponse:
    status_code = 200
    headers = {"content-type": "application/json"}

    def __init__(self, text):
        self.text = text


class FakeSession:
    def __init__(self, text):
        self.text = text
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return FakeResponse(self.text)


def test_wordpress_rest_normalizes_item_records():
    mod = load()
    old = mod.allowed_by_robots
    mod.allowed_by_robots = lambda url, ua: True
    session = FakeSession('[{"id": 7, "link": "https://example.org/ghost-1935", "title": {"rendered": "Ghost 1935"}, "excerpt": {"rendered": "A haunted station story"}, "date": "1935-01-01"}]')
    try:
        client = mod.WordpressRestClient(mod.EndpointConfig(rate_limit_seconds=0), session)
        rows = client.fetch_records({"endpoint_url": "https://example.org/wp-json/wp/v2/search?search={query}", "source_name": "Example", "source_tier": "B"}, {"query_text": "ghost"})
        assert rows[0].title == "Ghost 1935"
        assert rows[0].item_url == "https://example.org/ghost-1935"
        assert "ghost" in session.urls[0]
    finally:
        mod.allowed_by_robots = old


def test_disallowed_urls_never_fetch():
    mod = load()
    old = mod.allowed_by_robots
    mod.allowed_by_robots = lambda url, ua: True
    session = FakeSession("[]")
    try:
        client = mod.WordpressRestClient(mod.EndpointConfig(rate_limit_seconds=0), session)
        status, text, reason = client.get_text("https://api.trove.nla.gov.au/v3/result")
        assert status == 0
        assert text == ""
        assert reason == "disallowed_url"
        assert session.urls == []
    finally:
        mod.allowed_by_robots = old
