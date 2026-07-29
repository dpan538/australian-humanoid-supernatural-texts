import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("public_artifact_guard_mod", scripts / "assert_no_public_artifact_diff.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_public_artifact_guard_detects_frontend_diff_and_allows_explicit_override():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "public" / "data" / "frontend-data.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"a":1}\n')
        baseline = root / "baseline.json"
        created = mod.create_baseline(root, baseline)
        assert created["files"] == 1
        assert mod.check_baseline(root, baseline)["ok"] is True
        path.write_text('{"a":2}\n')
        try:
            mod.check_baseline(root, baseline)
            raised = False
        except SystemExit:
            raised = True
        assert raised is True
        allowed = mod.check_baseline(root, baseline, allow_changed=True)
        assert allowed["changed"] == ["public/data/frontend-data.json"]
