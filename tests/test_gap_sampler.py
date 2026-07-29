import csv
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_sampler():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "sample_gap_probe_jobs.py"
    spec = importlib.util.spec_from_file_location("sample_gap_probe_jobs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_priority_states_score_higher_than_lower_priority_states():
    sampler = load_sampler()
    route = {"source_tier": "A", "evidence_or_discovery": "evidence_possible", "mappability_likelihood": "high", "route_family": "state_library_catalogue", "base_url": "https://example.test", "access_method": "api"}
    wa_score, _ = sampler.score_query({"target_state": "WA", "time_band": "1940_1954"}, route)
    nsw_score, _ = sampler.score_query({"target_state": "NSW", "time_band": "1940_1954"}, route)
    assert wa_score > nsw_score


def test_discovery_only_rows_excluded_from_automated_fetch():
    sampler = load_sampler()
    route = {"source_id": "x", "source_tier": "E", "evidence_or_discovery": "discovery_only", "base_url": "https://example.test", "access_method": "api"}
    score, reasons = sampler.score_query({"target_state": "WA", "time_band": "1940_1954"}, route)
    assert score < 0
    assert "discovery_only_excluded" in reasons
    assert sampler.route_safety_class(route) == "discovery_only"


def test_manual_sensitive_rows_go_to_manual_batch():
    sampler = load_sampler()
    route = {"source_id": "x", "source_tier": "A", "evidence_or_discovery": "manual_only_sensitive", "base_url": "https://example.test", "access_method": "manual_catalogue_review"}
    assert sampler.route_safety_class(route) == "manual_sensitive"


def test_sample_is_deterministic_with_fixed_seed():
    sampler = load_sampler()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        query_plan = tmp_path / "queries.csv"
        fields = [
            "query_id",
            "time_band",
            "target_state",
            "query_string",
            "route_family",
            "preferred_source_ids_json",
        ]
        with query_plan.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({"query_id": "q1", "time_band": "1940_1954", "target_state": "WA", "query_string": "ghost", "route_family": "trove_newspaper_metadata", "preferred_source_ids_json": json.dumps(["trove_newspapers_gazettes"])})
            writer.writerow({"query_id": "q2", "time_band": "1940_1954", "target_state": "NSW", "query_string": "ghost", "route_family": "trove_newspaper_metadata", "preferred_source_ids_json": json.dumps(["trove_newspapers_gazettes"])})
        registry = tmp_path / "registry.yml"
        registry.write_text(
            """
- source_id: trove_newspapers_gazettes
  source_name: Trove
  institution: NLA
  route_family: trove_newspaper_metadata
  source_tier: A
  evidence_or_discovery: evidence_possible
  scope: national
  states: [WA, NSW]
  access_method: api
  base_url: https://api.trove.nla.gov.au/v3/result
  allowed_content_mode: metadata_first
""",
            encoding="utf-8",
        )
        targets = tmp_path / "targets.yml"
        targets.write_text("period_targets: {}\n", encoding="utf-8")
        out1 = tmp_path / "batch1.csv"
        out2 = tmp_path / "batch2.csv"
        rows1, _ = sampler.sample_jobs(query_plan, registry, targets, out1, 2, 42)
        rows2, _ = sampler.sample_jobs(query_plan, registry, targets, out2, 2, 42)
        assert [row["query_id"] for row in rows1] == [row["query_id"] for row in rows2]
