import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("item_level_test", scripts / "validate_item_level_candidate.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_item_page_with_title_date_term_passes():
    v = load()
    score, reasons = v.item_level_confidence(
        {"title": "1956 ghost record", "url": "https://example.test/record/1956-ghost-record", "snippet": "A ghost appeared in 1956."},
        metadata={"link_count": 4, "date": "1956"},
    )
    assert score >= 0.7


def test_directory_search_and_affiliate_pages_fail():
    v = load()
    for text in ["Search results browse all records", "Affiliate directory list of collection pages"]:
        score, reasons = v.item_level_confidence({"title": "Collection", "url": "https://example.test/search"}, text, {"link_count": 120})
        assert score < 0.7


def test_catalogue_item_and_pdf_record_pass_metadata_gate():
    v = load()
    cat_score, _ = v.item_level_confidence({"title": "Catalogue item haunted station 1962", "url": "https://example.test/catalogue/item/123"}, "Date 1962. Description haunted station.", {"link_count": 8})
    pdf_score, _ = v.item_level_confidence({"title": "Local history PDF ghost 1970", "url": "https://example.test/history/ghost-1970.pdf"}, "PDF date 1970 ghost", {"link_count": 2})
    assert cat_score >= 0.7
    assert pdf_score >= 0.7
