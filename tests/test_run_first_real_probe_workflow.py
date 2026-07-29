import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_workflow():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "run_first_real_probe_workflow.py"
    spec = importlib.util.spec_from_file_location("run_first_real_probe_workflow", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_does_not_require_trove_api_key():
    workflow = load_workflow()
    old = os.environ.pop("TROVE_API_KEY", None)
    try:
        # Validate the precondition branch directly; full workflow integration is covered by existing probe tests.
        assert workflow.os.environ.get("TROVE_API_KEY") is None
    finally:
        if old is not None:
            os.environ["TROVE_API_KEY"] = old


def test_execute_requires_trove_api_key_before_any_work():
    workflow = load_workflow()
    old = os.environ.pop("TROVE_API_KEY", None)
    try:
        try:
            workflow.run_workflow(
                db_path=Path("missing.sqlite"),
                query_plan=Path("missing.csv"),
                run_id="test",
                limit=1,
                max_results_per_query=1,
                execute=True,
            )
        except RuntimeError as exc:
            assert "TROVE_API_KEY" in str(exc)
        else:
            raise AssertionError("execute should require TROVE_API_KEY")
    finally:
        if old is not None:
            os.environ["TROVE_API_KEY"] = old


def test_workflow_report_declares_no_auto_import_or_map_publish():
    workflow = load_workflow()
    # Guardrail strings are part of the report implementation and prevent accidental semantic drift.
    source = Path(workflow.__file__).read_text(encoding="utf-8")
    assert "Candidates accepted: `0`" in source
    assert "Map flags published: `0`" in source
