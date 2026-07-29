import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("access_platform_endpoint_mod", scripts / "probe_noauth_access_platform_endpoints.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_access_platform_endpoint_wrapper_is_discovery_only():
    mod = load()
    old_mine = mod.mine
    mod.mine = lambda db, registry, run_id, out_dir, execute: {"candidates": 2, "decomposed": 1, "holds": 1}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            registry = tmp_path / "registry.yml"
            registry.write_text("[]\n", encoding="utf-8")
            summary = mod.run(tmp_path / "db.sqlite", registry, "run", tmp_path / "out", True)
            assert summary["candidates"] == 2
            assert summary["public_mutation"] is False
            assert (tmp_path / "out" / "access_platform_endpoint_report.md").exists()
    finally:
        mod.mine = old_mine
