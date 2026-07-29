import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("discover_forms_test", scripts / "discover_noauth_search_forms.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_fetch_timeout_is_recorded_and_does_not_abort():
    d = load()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        seeds = root / "seeds.yml"
        out = root / "forms.csv"
        report = root / "forms.md"
        seeds.write_text(
            """
- route_id: slow_route
  source_id: slow_route
  source_name: Slow Official Site
  source_tier: A
  route_family: state_library_catalogue
  state: WA
  official_url: https://slow.example.test/
  evidence_or_discovery: evidence_possible
""",
            encoding="utf-8",
        )
        d.quick_allowed_by_robots = lambda *args, **kwargs: True

        def boom(*args, **kwargs):
            raise TimeoutError("slow")

        d.fetch_html_quick = boom
        rows = d.discover(seeds, out, report, execute=True)
        assert rows == []
        assert "fetch_exception_or_timeout" in report.read_text(encoding="utf-8")
