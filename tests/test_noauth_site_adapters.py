import importlib.util
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return importlib.import_module("adapters.noauth_sites.generic")


HTML = """
<html><head><title>Ghost newsletter 1968</title></head>
<body>
<a href="/item/1">Ghost newsletter Vol. 5 1968</a>
<a href="/files/newsletter-1968.pdf">Newsletter PDF 1968 ghost</a>
</body></html>
"""


def test_generic_adapters_parse_results_items_and_pdf_index_without_pagination():
    g = load()
    adapter = g.GenericPDFIndexAdapter()
    results = adapter.parse_result_page(HTML, "https://example.test/index", {"route_family": "local_history_serial"})
    item = adapter.parse_item_page(HTML, "https://example.test/item/1", {})
    pdfs = adapter.extract_pdf_links(HTML, "https://example.test/index")
    assert results
    assert item.title == "Ghost newsletter 1968"
    assert len(pdfs) == 1
    assert pdfs[0].date_text == "1968"


def test_wordpress_drupal_omeka_atom_build_search_urls():
    g = load()
    route = {"official_url": "https://example.test/"}
    assert "/?s=ghost" in g.WordPressAdapter().build_search_urls(route, "ghost")[0]
    assert "/search/node/ghost" in g.DrupalAdapter().build_search_urls(route, "ghost")[0]
    assert "/items/browse?search=ghost" in g.OmekaAdapter().build_search_urls(route, "ghost")[0]
    assert "informationobject" in g.AtoMAdapter().build_search_urls(route, "ghost")[0]
