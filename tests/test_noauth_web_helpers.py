import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "lib" / "noauth_web.py"
    spec = importlib.util.spec_from_file_location("noauth_web", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_robots_failure_returns_disallowed():
    mod = load_module()
    original = mod.read_robots
    try:
        mod.read_robots = lambda _url: None
        assert mod.allowed_by_robots("https://example.test/page") is False
    finally:
        mod.read_robots = original


def test_fetch_refuses_non_html():
    mod = load_module()

    class Response:
        status_code = 200
        text = "%PDF"
        headers = {"content-type": "application/pdf"}

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    original = mod.allowed_by_robots
    try:
        mod.allowed_by_robots = lambda *_args, **_kwargs: True
        route = mod.RouteSafety(route_id="r", rate_limit_seconds=0)
        assert mod.fetch_html_safe("https://example.test/file.pdf", route, Session()) is None
    finally:
        mod.allowed_by_robots = original


def test_same_domain_jsonld_and_pdf_links():
    mod = load_module()
    html = """
    <html><head>
    <script type="application/ld+json">{"name":"Haunted gaol","datePublished":"1960"}</script>
    </head><body><a href="/x.pdf">History PDF</a></body></html>
    """
    assert mod.same_domain("https://example.test/a", "https://example.test/b")
    assert not mod.same_domain("https://example.test/a", "https://other.test/b")
    assert mod.extract_jsonld(html)[0]["name"] == "Haunted gaol"
    assert mod.extract_pdf_links(html, "https://example.test/page")[0]["url"] == "https://example.test/x.pdf"
