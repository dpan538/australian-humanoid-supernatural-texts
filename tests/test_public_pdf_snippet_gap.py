import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("pdf_gap_test", scripts / "probe_public_pdf_snippets_gap.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_pdf_snippet_stores_only_matched_context_not_body():
    p = load()
    text = "x" * 1000 + "In 1965 a ghost appeared near the old station." + "y" * 1000
    snippets = p.extract_snippets(text, ["ghost"], radius=40)
    assert len(snippets) == 1
    assert "1965" in snippets[0]
    assert "ghost" in snippets[0]
    assert len(snippets[0]) < len(text)
    assert p.extract_issue_date_text("newsletter-1968.pdf", "ghost") == "1968"


def test_pdf_policy_rejects_non_pdf_api_and_non_abc():
    p = load()
    assert p.safe_pdf_url("https://example.test/file.html", {"safety": {}}, "A")[1] == "not_pdf"
    assert p.safe_pdf_url("https://example.test/api/file.pdf", {"safety": {}}, "A")[1] == "api_url_rejected"
    assert p.safe_pdf_url("https://example.test/file.pdf", {"safety": {}}, "D")[1] == "source_tier_not_abc"
