import csv
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_probe_plan():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "plan_first_real_probe.py"
    spec = importlib.util.spec_from_file_location("plan_first_real_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_registry(path: Path) -> None:
    path.write_text(
        """
- source_id: trove_newspapers_gazettes
  source_name: Trove Newspapers
  institution: NLA
  route_family: trove_newspaper_metadata
  source_tier: A
  evidence_or_discovery: evidence_possible
  scope: national
  states: [WA, SA, NT, TAS, ACT, NSW]
  access_method: api
  base_url: https://api.trove.nla.gov.au/v3/result
  allowed_content_mode: metadata_first
- source_id: manual_sensitive
  source_name: Manual
  institution: Manual
  route_family: manual
  source_tier: A
  evidence_or_discovery: manual_only_sensitive
  scope: national
  states: [WA]
  access_method: manual
  allowed_content_mode: manual_only
""",
        encoding="utf-8",
    )


def test_first_real_probe_is_limited_trove_metadata_and_priority_states():
    planner = load_probe_plan()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        query_plan = tmp_path / "queries.csv"
        fields = ["query_id", "time_band", "target_state", "target_locality", "route_family", "preferred_source_ids_json", "route_source_tier", "should_fetch", "should_manual_review", "route_safety_class"]
        with query_plan.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for i in range(60):
                writer.writerow(
                    {
                        "query_id": f"q{i}",
                        "time_band": ["1926_1939", "1940_1954", "1955_1964", "1965_1976"][i % 4],
                        "target_state": ["WA", "SA", "NT", "TAS", "ACT", "NSW"][i % 6],
                        "target_locality": "Perth" if i % 2 == 0 else "",
                        "route_family": "trove_newspaper_metadata",
                        "preferred_source_ids_json": json.dumps(["trove_newspapers_gazettes"]),
                        "route_source_tier": "A",
                        "should_fetch": "true",
                        "should_manual_review": "false",
                        "route_safety_class": "automated_metadata_api",
                    }
                )
            writer.writerow(
                {
                    "query_id": "manual",
                    "time_band": "1940_1954",
                    "target_state": "WA",
                    "target_locality": "",
                    "route_family": "manual",
                    "preferred_source_ids_json": json.dumps(["manual_sensitive"]),
                    "route_source_tier": "A",
                    "should_fetch": "false",
                    "should_manual_review": "true",
                    "route_safety_class": "manual_sensitive",
                }
            )
        registry = tmp_path / "registry.yml"
        write_registry(registry)
        rows = planner.plan_probe(query_plan, registry, tmp_path / "out.csv", tmp_path / "report.md", 50)
        assert len(rows) == 50
        assert all(row["route_family"] == "trove_newspaper_metadata" for row in rows)
        assert all(row["route_source_tier"] == "A" for row in rows)
        assert all(row["target_state"] in {"WA", "SA", "NT", "TAS", "ACT", "NSW"} for row in rows)
        assert "manual" not in {row["query_id"] for row in rows}
        assert rows[0]["target_state"] in {"WA", "SA", "NT", "TAS", "ACT"}
