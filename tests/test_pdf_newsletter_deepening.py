import csv
import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("pdf_deepening_mod", scripts / "deepen_viable_pdf_newsletter_routes.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_viable_pdf_and_newsletter_routes_are_selected_from_viability_candidates():
    mod = load()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root / "viability_candidates.csv"
        fields = ["route_id", "url", "title", "route_family", "item_format", "source_name", "source_tier"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({"route_id": "r1", "url": "https://example.test/newsletter.pdf", "title": "Newsletter 1968", "route_family": "local_history_serial", "item_format": "PDF_ISSUE", "source_name": "S", "source_tier": "B"})
            writer.writerow({"route_id": "r2", "url": "https://example.test/page", "title": "Generic page", "route_family": "heritage_register", "item_format": "ARTICLE_PAGE", "source_name": "S", "source_tier": "B"})
        routes = mod.candidate_routes(root, 20)
        assert [r["route_id"] for r in routes] == ["r1"]


def test_non_pdf_and_image_only_paths_do_not_create_snippets_without_fetch():
    mod = load()
    assert mod.fetch_pdf_snippets("https://example.test/page.html", type("Cfg", (), {"user_agent": "t", "data": {}})(), None, ["ghost"])[1] == "not_pdf"
