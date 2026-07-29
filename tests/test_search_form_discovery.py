import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("search_form_discovery_test", scripts / "discover_noauth_search_forms.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_get_form_accepted_and_post_login_captcha_rejected():
    d = load()
    html = """
    <form method="get" action="/search"><input name="query"></form>
    <form method="post" action="/search"><input name="q"></form>
    <form method="get" action="/login"><input type="password" name="password"></form>
    <form method="get" action="/search"><input name="captcha"><input name="q"></form>
    """
    rows = d.form_candidates(html, "https://example.test/")
    assert len(rows) == 1
    assert rows[0]["method"] == "GET"


def test_common_cms_templates_detected():
    d = load()
    templates = [row["search_url_template"] for row in d.template_candidates("https://example.test/base")]
    assert "https://example.test/?s={query}" in templates
    assert "https://example.test/index.php/informationobject/browse?topLod=0&query={query}" in templates
    assert "https://example.test/items/browse?search={query}" in templates
