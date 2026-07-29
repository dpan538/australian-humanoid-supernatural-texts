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
    path = scripts / "noauth_evaluate_route_yield.py"
    spec = importlib.util.spec_from_file_location("noauth_evaluate_route_yield", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_scores(path: Path, rows):
    fields = ["candidate_id", "route_id", "source_name", "target_state", "time_band", "machine_bucket", "machine_reasons"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def test_high_priority_rate_expands_route():
    mod = load_module()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        scores = base / "scores.csv"
        out = base / "out.csv"
        report = base / "report.md"
        write_scores(scores, [{"candidate_id": f"c{i}", "route_id": "r", "target_state": "WA", "time_band": "1955_1964", "machine_bucket": "PRIORITY_REVIEW_OPEN_RECORD"} for i in range(3)])
        mod.evaluate(scores, out, report)
        assert list(csv.DictReader(out.open(encoding="utf-8")))[0]["recommended_action"] == "EXPAND_NOAUTH_ROUTE"


def test_noise_and_robots_pause_routes():
    mod = load_module()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        scores = base / "scores.csv"
        out = base / "out.csv"
        report = base / "report.md"
        rows = [{"candidate_id": f"n{i}", "route_id": "noise", "machine_bucket": "EXCLUDE_CONTEXT_NOISE"} for i in range(3)]
        rows.append({"candidate_id": "r1", "route_id": "robots", "machine_bucket": "HOLD", "machine_reasons": "robots_unconfirmed"})
        write_scores(scores, rows)
        mod.evaluate(scores, out, report)
        actions = {row["route_id"]: row["recommended_action"] for row in csv.DictReader(out.open(encoding="utf-8"))}
        assert actions["noise"] == "PAUSE_NOISE"
        assert actions["robots"] == "PAUSE_ROBOTS_OR_TERMS"


def test_low_yield_promising_retries():
    mod = load_module()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        scores = base / "scores.csv"
        out = base / "out.csv"
        report = base / "report.md"
        write_scores(scores, [{"candidate_id": "c", "route_id": "r", "machine_bucket": "PROMISING_SOURCE_ROUTE"}])
        mod.evaluate(scores, out, report)
        assert list(csv.DictReader(out.open(encoding="utf-8")))[0]["recommended_action"] == "RETRY_WITH_BETTER_QUERY"
