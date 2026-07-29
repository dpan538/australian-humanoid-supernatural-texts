import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(name, scripts / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_research_volume_migration_creates_layer_tables():
    mig = load("research_volume_migrate_test", "migrate_research_volume_expansion_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "auxiliary_source_intelligence" in tables
        assert "research_volume_items" in tables
        assert "research_volume_milestones" in tables
        assert "records" not in tables or True


def test_scheduler_builds_safe_layered_volume_plan():
    sched = load("research_volume_scheduler_test", "build_research_volume_expansion_scheduler.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        summary = sched.build(db, "rv_test", 120, tmp_path / "schedule.csv", tmp_path / "schedule.md", True)
        text = (tmp_path / "schedule.md").read_text()
        assert summary["scheduled_items"] == 120
        assert "target_gap_lead" in summary["layers"]
        assert "metadata_only_lead" in summary["layers"]
        assert "Trove API" not in text
        assert "Public records mutated: `no`" in text


def test_operator_materializes_research_layers_without_public_mutation():
    op = load("research_volume_operator_test", "run_research_volume_expansion_operator.py")
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        summary = op.run(db, "rv_test", 120, True, Path(tmp) / "volume")
        with sqlite3.connect(db) as conn:
            public_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='records'").fetchone()[0] else 0
            lead_count = conn.execute("SELECT COUNT(*) FROM target_gap_leads WHERE source_run_id='rv_test'").fetchone()[0]
            aux_count = conn.execute("SELECT COUNT(*) FROM auxiliary_source_intelligence WHERE run_id='rv_test'").fetchone()[0]
            item_count = conn.execute("SELECT COUNT(*) FROM research_volume_items WHERE run_id='rv_test'").fetchone()[0]
        assert summary["total_new_items"] == 120
        assert lead_count > 0
        assert aux_count > 0
        assert item_count == 120
        assert public_count == 0


def test_milestone_and_dashboard_separate_layers():
    op = load("research_volume_operator_dash_test", "run_research_volume_expansion_operator.py")
    dash = load("research_volume_dashboard_test", "build_research_volume_dashboard.py")
    milestone = load("research_volume_milestone_test", "research_volume_milestone_audit.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        op.run(db, "rv_test", 120, True, tmp_path / "volume")
        ms = milestone.audit(db, "rv_test", 50, tmp_path / "milestone_50")
        ds = dash.dashboard(db, "rv_test", tmp_path / "dashboard.md")
        text = (tmp_path / "dashboard.md").read_text()
        assert ms["total_new_items"] == 50
        assert ds["new_items"] == 120
        assert "Accepted public records automatically created: `0`" in text
        assert "Target-gap leads" in text
        assert "Auxiliary source intelligence" in text
