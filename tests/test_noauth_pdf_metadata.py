import csv
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "noauth_probe_pdf_metadata.py"
    spec = importlib.util.spec_from_file_location("noauth_probe_pdf_metadata", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_plan(path: Path):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["route_id", "source_name", "target_state", "query_string", "official_url", "search_url"])
        writer.writeheader()
        writer.writerow({"route_id": "r", "source_name": "Source", "target_state": "WA", "query_string": "ghost Perth", "official_url": "https://example.test/page", "search_url": "https://example.test/page"})


def test_pdf_links_recorded_without_text_extraction():
    mod = load_module()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        plan = base / "plan.csv"
        out = base / "pdf.csv"
        report = base / "report.md"
        write_plan(plan)
        original_allowed = mod.allowed_by_robots
        original_fetch = mod.fetch_html_safe
        original_head = mod.head_pdf
        try:
            mod.allowed_by_robots = lambda *_args, **_kwargs: True
            mod.fetch_html_safe = lambda *_args, **_kwargs: "<a href='/x.pdf'>Local history PDF</a>"
            mod.head_pdf = lambda *_args, **_kwargs: {"content_type": "application/pdf", "content_length": "123", "last_modified": "today", "relevance_signals": "pdf_link_metadata_only"}
            summary = mod.run(plan, out, report, 10, execute=True)
        finally:
            mod.allowed_by_robots = original_allowed
            mod.fetch_html_safe = original_fetch
            mod.head_pdf = original_head
        rows = list(csv.DictReader(out.open(encoding="utf-8")))
        assert summary["rows"] == 1
        assert rows[0]["pdf_url"] == "https://example.test/x.pdf"
        assert "PDF text extracted: `no`" in report.read_text(encoding="utf-8")


def test_head_failure_does_not_crash():
    mod = load_module()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        plan = base / "plan.csv"
        out = base / "pdf.csv"
        report = base / "report.md"
        write_plan(plan)
        original_allowed = mod.allowed_by_robots
        original_fetch = mod.fetch_html_safe
        original_head = mod.head_pdf
        try:
            mod.allowed_by_robots = lambda *_args, **_kwargs: True
            mod.fetch_html_safe = lambda *_args, **_kwargs: "<a href='/x.pdf'>PDF</a>"
            mod.head_pdf = lambda *_args, **_kwargs: {"content_type": "", "content_length": "", "last_modified": "", "relevance_signals": "pdf_head_failed"}
            summary = mod.run(plan, out, report, 10, execute=True)
        finally:
            mod.allowed_by_robots = original_allowed
            mod.fetch_html_safe = original_fetch
            mod.head_pdf = original_head
        assert summary["rows"] == 1
