import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("robots_rescue_operator_mod", scripts / "run_robots_aware_near_miss_rescue_operator.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def patch_common(mod, calls, safe_alts=0, targets=0, remaining=0):
    mod.create_baseline = lambda *_args, **_kwargs: calls.append("baseline") or {"files": 1}
    mod.check_baseline = lambda *_args, **_kwargs: calls.append("artifact_check") or {"ok": True}
    mod.audit_robots = lambda *_args, **_kwargs: calls.append("audit") or {"robots_status_counts": {"ROBOTS_UNKNOWN_MISSING_ROBOTS": 1}}
    mod.enrich_existing_metadata = lambda *_args, **_kwargs: calls.append("existing") or {"target_gap_records": 0}
    mod.repair_atom = lambda *_args, **_kwargs: calls.append("atom") or {"target_gap_records": 0}
    mod.enrich_rss_inline = lambda *_args, **_kwargs: calls.append("rss") or {"target_gap_records": 0}
    mod.discover_alternatives = lambda *_args, **_kwargs: calls.append("alternatives") or {"safe_to_fetch": safe_alts}
    mod.enrich_alternatives = lambda *_args, **_kwargs: calls.append("enrich_alt") or {"target_gap_records": 0}
    mod.checkpoint = lambda *_args, **_kwargs: calls.append("checkpoint") or {}
    mod.run_watchdog = lambda *_args, **_kwargs: calls.append("watchdog") or {"hard": 0}
    mod.db_counts = lambda *_args, **_kwargs: {"materialized_near_misses": 120, "target_gap_records": targets, "recoverable_remaining": remaining}


def test_operator_runs_phases_and_continues_for_safe_alternatives():
    mod = load()
    calls = []
    patch_common(mod, calls, safe_alts=3, targets=0, remaining=120)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.STRUCTURED_DIR = tmp_path / "structured"
        mod.REVIEW_DIR = tmp_path / "review"
        mod.BASELINE = tmp_path / "baseline.json"
        mod.SUMMARY = tmp_path / "summary.md"
        summary = mod.run_operator(tmp_path / "test.sqlite", "run", 2000, True)
    assert calls[:8] == ["baseline", "audit", "existing", "atom", "rss", "alternatives", "enrich_alt", "checkpoint"]
    assert summary["stop_status"] == "continue_structured_enrichment"


def test_operator_reports_target_records_found():
    mod = load()
    calls = []
    patch_common(mod, calls, safe_alts=0, targets=2, remaining=0)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.STRUCTURED_DIR = tmp_path / "structured"
        mod.REVIEW_DIR = tmp_path / "review"
        mod.BASELINE = tmp_path / "baseline.json"
        mod.SUMMARY = tmp_path / "summary.md"
        summary = mod.run_operator(tmp_path / "test.sqlite", "run", 2000, True)
    assert summary["stop_status"] == "target_gap_records_found"
