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
    spec = importlib.util.spec_from_file_location("viability_test_mod", scripts / "run_target_acquisition_viability_test.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class Result:
    def __init__(self, i, target=True):
        self.title = f"Ghost newsletter 1968 {i}" if target else f"Local history {i}"
        self.url = f"https://example.test/item/{i}"
        self.snippet = "A ghost story in the 1968 issue." if target else "Local history article."
        self.date_text = "1968" if target else ""
        self.item_format = "SERIAL_ISSUE_ITEM"


class Adapter:
    def __init__(self, target=True):
        self.target = target

    def parse_result_page(self, html, url, route):
        return [Result(i, self.target) for i in range(10)]

    def extract_pdf_links(self, html, url):
        return []


def write_plan(path):
    fields = ["action_id", "action_type", "route_id", "source_name", "source_tier", "route_family", "state", "official_url", "target_url_or_template", "query_string", "target_time_band", "target_locality", "term_family", "term", "expected_target_signal", "why_selected", "should_fetch", "should_pdf_snippet", "should_use_search_form", "should_use_adapter", "priority_score", "safety_notes"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i in range(2):
            writer.writerow({"action_id": f"a{i}", "action_type": "PROBE_NEWSLETTER_ARCHIVE", "route_id": "r", "source_name": "Source", "source_tier": "A", "route_family": "local_history_serial", "state": "WA", "official_url": "https://example.test", "target_url_or_template": "https://example.test/search?q={query}", "query_string": "ghost 1968", "target_time_band": "1965_1976", "target_locality": "WA", "term_family": "controlled", "term": "ghost", "expected_target_signal": "", "why_selected": "", "should_fetch": "1", "should_pdf_snippet": "0", "should_use_search_form": "1", "should_use_adapter": "1", "priority_score": "100", "safety_notes": ""})


def test_viability_passes_with_ten_target_records_and_fails_for_auxiliary_only():
    v = load()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        plan = root / "plan.csv"
        write_plan(plan)
        v.fetch_public_html = lambda *args, **kwargs: ("<html>ghost 1968</html>", "ok")
        v.matching_adapters = lambda *args, **kwargs: [Adapter(target=True)]
        v.VIABILITY_DIR = root / "viability_good"
        good = v.run_viability(root / "good.sqlite", plan, "run_good", 2, execute=True)
        assert good["viable"]
        assert good["target_records"] >= 10
        v.matching_adapters = lambda *args, **kwargs: [Adapter(target=False)]
        v.VIABILITY_DIR = root / "viability_bad"
        bad = v.run_viability(root / "bad.sqlite", plan, "run_bad", 2, execute=True)
        assert not bad["viable"]
        assert bad["target_records"] == 0


def test_viability_fails_safely_when_robots_denied():
    v = load()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        plan = root / "plan.csv"
        write_plan(plan)
        v.fetch_public_html = lambda *args, **kwargs: ("", "robots_denied_or_unknown")
        v.VIABILITY_DIR = root / "viability_robots"
        result = v.run_viability(root / "robots.sqlite", plan, "run_robots", 2, execute=True)
        assert not result["viable"]
        assert result["failed_actions"] == 2
