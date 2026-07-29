import csv
import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel, name):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(name, scripts / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_get_search_forms_build_gap_queries_and_prioritize_late_priority_states():
    builder = load(Path("build_gap_targeted_noauth_frontier.py"), "gap_frontier_builder_test")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        db = root / "db.sqlite"
        config = root / "config.yml"
        seeds = root / "seeds.yml"
        forms = root / "forms.csv"
        out = root / "plan.md"
        config.write_text(
            """
run_name: gap
target: {target_gap_effective_records: 2000}
term_gate: {controlled_terms: [ghost, "haunted hotel"]}
priority:
  states: {WA: 70, NSW: 10}
  route_families: {local_history_serial: 80}
outputs: {reports_dir: out}
""",
            encoding="utf-8",
        )
        seeds.write_text(
            """
- route_id: wa_route
  source_id: wa_route
  source_name: WA History
  source_tier: A
  route_family: local_history_serial
  state: WA
  official_url: https://wa.example/search
  evidence_or_discovery: evidence_possible
- route_id: bad_api
  source_id: bad_api
  source_name: Trove API
  source_tier: A
  route_family: state_library_catalogue
  state: NSW
  official_url: https://api.trove.nla.gov.au/v3/result
  evidence_or_discovery: evidence_possible
""",
            encoding="utf-8",
        )
        with forms.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["route_id", "source_name", "state", "search_url_template", "method", "query_param", "confidence", "reason", "robots_status", "safe_to_use"])
            writer.writeheader()
            writer.writerow({"route_id": "wa_route", "source_name": "WA History", "state": "WA", "search_url_template": "https://wa.example/search?q={query}", "method": "GET", "query_param": "q", "confidence": "0.9", "reason": "safe", "robots_status": "allowed", "safe_to_use": "1"})
        summary = builder.build_frontier(db, config, seeds, forms, "run", out, execute=True)
        assert summary["search_query_rows"] > 0
        assert summary["rejected"] == 1
        with sqlite3.connect(db) as conn:
            rows = conn.execute("SELECT url, priority_score FROM harvest_frontier WHERE run_id='run'").fetchall()
        assert rows
        assert any("1955" in row[0] or "1960s" in row[0] or "1970s" in row[0] for row in rows)
        assert max(row[1] for row in rows) > 100
