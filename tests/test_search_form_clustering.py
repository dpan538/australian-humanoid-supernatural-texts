import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("search_form_repair_mod", scripts / "cluster_and_repair_search_forms.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_get_wordpress_drupal_omeka_atom_templates_are_recognized():
    mod = load()
    base = {"method": "GET", "safe_to_use": "1", "safe_to_probe": "1", "source_name": "History"}
    assert mod.cluster_form({**base, "search_url_template": "https://x.test/?s={query}"})[0] == "WORDPRESS"
    assert mod.cluster_form({**base, "search_url_template": "https://x.test/search/node/{query}"})[0] == "DRUPAL"
    assert mod.cluster_form({**base, "search_url_template": "https://x.test/items/browse?search={query}"})[0] == "OMEKA"
    assert mod.cluster_form({**base, "search_url_template": "https://x.test/index.php/informationobject/browse?query={query}"})[0] == "ATOM"


def test_login_post_and_unsafe_forms_are_paused():
    mod = load()
    assert mod.cluster_form({"method": "POST", "safe_to_use": "1", "search_url_template": "https://x.test/search"})[0] == "POST_FORM"
    assert mod.cluster_form({"method": "GET", "safe_to_use": "1", "search_url_template": "https://x.test/login?token={query}"})[0] == "LOGIN_OR_AUTH"
    assert mod.cluster_form({"method": "GET", "safe_to_use": "0", "search_url_template": "https://x.test/search?q={query}"})[0] == "UNKNOWN_UNSAFE"
