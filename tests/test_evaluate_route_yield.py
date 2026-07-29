import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_eval():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "evaluate_route_yield.py"
    spec = importlib.util.spec_from_file_location("evaluate_route_yield", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_healthy_route_recommends_continue_small_batch():
    evaluator = load_eval()
    rows = [{"candidate_id": f"c{i}", "source_id": "trove", "source_name": "Trove", "target_state": "WA", "time_band": "1940_1954", "machine_bucket": "PRIORITY_REVIEW" if i < 3 else "HOLD"} for i in range(20)]
    result = evaluator.evaluate(rows, [])[0]
    assert result["recommended_action"] == "CONTINUE_SMALL_BATCH"


def test_noisy_route_recommends_pause_noise():
    evaluator = load_eval()
    rows = [{"candidate_id": f"c{i}", "source_id": "x", "source_name": "Noisy", "target_state": "NSW", "time_band": "1940_1954", "machine_bucket": "EXCLUDE_CONTEXT_NOISE" if i < 13 else "HOLD"} for i in range(20)]
    result = evaluator.evaluate(rows, [])[0]
    assert result["recommended_action"] == "PAUSE_NOISE"


def test_many_poor_chains_recommends_source_chain_repair():
    evaluator = load_eval()
    rows = [{"candidate_id": f"c{i}", "source_id": "x", "source_name": "Source", "target_state": "SA", "time_band": "1955_1964", "machine_bucket": "ROUTE_YIELD_SIGNAL"} for i in range(9)]
    source_rows = [{"candidate_id": f"c{i}", "machine_bucket": "RED_DISCOVERY_ONLY_LEAKAGE"} for i in range(4)]
    result = evaluator.evaluate(rows, source_rows)[0]
    assert result["recommended_action"] == "NEEDS_SOURCE_CHAIN_REPAIR"
