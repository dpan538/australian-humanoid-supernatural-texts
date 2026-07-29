import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("constraint_sim_mod", scripts / "simulate_constraint_relaxation.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_constraint_scenarios_are_decision_support_only():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        summary = mod.simulate(db, ROOT / "config" / "constraint_decision.yml", tmp_path / "sim.md", True)
        with sqlite3.connect(db) as conn:
            rows = {row[0]: row for row in conn.execute("SELECT scenario_name, expected_new_records, expected_new_leads, recommendation, owner_effort FROM constraint_relaxation_scenarios").fetchall()}
        assert summary["scenarios"] == 10
        assert rows["Strict no-credential remains unchanged"][1] == 0
        assert rows["Allow target-gap leads as observational layer"][2] > 0
        assert "requires key" in rows["Allow Trove API key for 1926-1954 only"][3]
        assert rows["Allow top-25 machine-selected human review"][4] == "low"
        assert "No scenario was executed" in (tmp_path / "sim.md").read_text()
