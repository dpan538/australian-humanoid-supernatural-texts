import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("target_operator_test", scripts / "target_acquisition_operator.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_operator_does_not_resume_when_viability_fails_and_resumes_when_viable():
    op = load()
    with tempfile.TemporaryDirectory() as temp:
        db = Path(temp) / "db.sqlite"
        config = Path(temp) / "config.yml"
        config.write_text("{}", encoding="utf-8")
        op.ROOT = Path(temp)
        op.analyze = lambda *args, **kwargs: {"candidates": 10}
        op.discover = lambda *args, **kwargs: []
        op.build_plan = lambda *args, **kwargs: [{"action_id": "a"}]
        op.run_viability = lambda *args, **kwargs: {"target_records": 0, "near_misses": 0, "viable_pdf_routes": 0, "viable": False}
        called = {"resume": 0}
        op.supervise = lambda *args, **kwargs: called.update(resume=called["resume"] + 1) or {}
        result = op.run_operator(db, config, "run", 2000, execute=True)
        assert not result["resumed"]
        assert called["resume"] == 0
        op.run_viability = lambda *args, **kwargs: {"target_records": 10, "near_misses": 0, "viable_pdf_routes": 0, "viable": True}
        result = op.run_operator(db, config, "run", 2000, execute=True)
        assert result["resumed"]
        assert called["resume"] == 1
