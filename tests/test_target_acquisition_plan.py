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
    spec = importlib.util.spec_from_file_location("target_plan_test", scripts / "build_target_acquisition_plan.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_plan_selects_target_actions_and_pauses_auxiliary_routes():
    p = load()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        post = root / "post"
        post.mkdir()
        (post / "route_surface_diagnosis.csv").write_text("route_id,recommended_action,surface_diagnosis\nwa_serial,PAUSE_AUXILIARY_ONLY_ROUTE,PROBE_NEWSLETTER_ARCHIVE\n", encoding="utf-8")
        seeds = root / "seeds.yml"
        seeds.write_text(
            """
- route_id: wa_serial
  source_id: wa_serial
  source_name: WA Newsletter
  source_tier: A
  route_family: local_history_serial
  state: WA
  official_url: https://wa.example.test/newsletters
  evidence_or_discovery: evidence_possible
- route_id: sensitive
  source_id: sensitive
  source_name: Sensitive
  source_tier: A
  route_family: local_history_serial
  state: WA
  official_url: https://sensitive.example.test
  evidence_or_discovery: manual_only_sensitive
""",
            encoding="utf-8",
        )
        out = root / "plan.csv"
        report = root / "report.md"
        rows = p.build_plan(root / "db.sqlite", post, seeds, root / "registry.yml", root / "matrix.yml", out, report, 100)
        types = {row["action_type"] for row in rows}
        assert "PROBE_NEWSLETTER_ARCHIVE" in types
        assert "PAUSE_AUXILIARY_ONLY_ROUTE" in types
        assert "manual_only_sensitive" not in out.read_text(encoding="utf-8")
        assert rows[0]["state"] == "WA"
        assert any(row["target_time_band"] in {"1955_1964", "1965_1976"} for row in rows)
