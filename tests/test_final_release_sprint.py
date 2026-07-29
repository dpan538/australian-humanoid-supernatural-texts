import importlib.util
import json
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


def test_release_freeze_inputs_marks_crawlers_frozen():
    mod = load("freeze_release_inputs_test", "freeze_release_inputs.py")
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.sqlite"
        summary = mod.freeze(db, Path(tmp) / "freeze", True)
        assert summary["crawler_status"] == "frozen"
        assert "long_marathon" in summary["disallowed_post_freeze_actions"]
        assert (Path(tmp) / "freeze" / "freeze_state.json").exists()


def test_1926_2011_release_coverage_detects_critical_gap_and_separates_layers():
    mod = load("release_coverage_test", "build_1926_2011_release_coverage.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        freeze = tmp_path / "freeze.json"
        freeze.write_text(json.dumps({"freeze_id": "t"}))
        db = tmp_path / "test.sqlite"
        summary = mod.build(db, freeze, tmp_path / "coverage", True)
        gaps = (tmp_path / "coverage" / "hard_gap_report.md").read_text()
        assert summary["critical_hard_gaps"] > 0
        assert "CRITICAL_HARD_GAP" in gaps
        assert "Metadata-only and lead layers are not accepted public records" in (tmp_path / "coverage" / "release_coverage_1926_2011_summary.md").read_text()


def test_bounded_patch_plan_cap_and_priority_from_existing_layers():
    rv = load("rv_op_patch_test", "run_research_volume_expansion_operator.py")
    mod = load("bounded_patch_test", "build_bounded_patch_plan_1926_2011.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        rv.run(db, "rv_patch", 120, True, tmp_path / "rv")
        summary = mod.build(db, tmp_path, tmp_path / "patch.csv", tmp_path / "patch.md", 25, True)
        text = (tmp_path / "patch.md").read_text()
        assert summary["selected"] == 25
        assert "Public record autopromotion: `no`" in text


def test_release_layers_patch_inserts_only_internal_layers():
    rv = load("rv_op_release_layer_test", "run_research_volume_expansion_operator.py")
    plan = load("bounded_patch_release_layer_test", "build_bounded_patch_plan_1926_2011.py")
    apply = load("apply_patch_release_layer_test", "apply_bounded_patch_to_release_layers.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        rv.run(db, "rv_patch", 80, True, tmp_path / "rv")
        plan.build(db, tmp_path, tmp_path / "patch.csv", tmp_path / "patch.md", 20, True)
        summary = apply.apply_patch_rows(db, tmp_path / "patch.csv", "patch_test", True, tmp_path / "apply")
        with sqlite3.connect(db) as conn:
            records_exists = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='records'").fetchone()[0]
            public_bad = conn.execute("SELECT COUNT(*) FROM release_metadata_gap_items WHERE public_record_status!='not_public_record'").fetchone()[0]
        assert summary["inserted"] == 20
        assert records_exists == 0
        assert public_bad == 0


def test_final_map_layers_keep_public_map_and_overlays_separate():
    migrate = load("release_layer_migrate_map_test", "migrate_release_layers_v1.py")
    mod = load("final_map_layers_test", "build_final_map_layers.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        migrate.migrate(db)
        frontend = tmp_path / "frontend-data.json"
        frontend.write_text(json.dumps({"map_points": [{"record_id": 1, "title": "Accepted", "lat": -35, "lng": 149}]}))
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO release_metadata_gap_items (release_item_id,title,target_state,target_locality,place_signal,public_record_status,map_display_status,created_at,updated_at) VALUES ('m','Meta','WA','Albany','Albany','not_public_record','not_public_map','now','now')")
            conn.execute("INSERT INTO release_lead_overlay_items (release_lead_id,title,target_state,target_locality,public_record_status,map_display_status,created_at,updated_at) VALUES ('l','Lead','SA','Burra','not_public_record','not_public_map','now','now')")
            conn.commit()
        summary = mod.build(db, frontend, tmp_path / "map", True)
        assert summary["accepted_public_map"] == 1
        assert summary["metadata_place_overlay"] == 1
        assert summary["lead_place_overlay"] == 1


def test_redirect_registry_validation_detects_loops_and_preserves_urls():
    mig = load("redirect_migrate_test", "migrate_redirect_registry_v1.py")
    val = load("redirect_validate_test", "validate_redirect_registry.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE target_gap_leads (lead_id TEXT PRIMARY KEY)")
            conn.executemany("INSERT INTO target_gap_leads VALUES (?)", [("a",), ("b",)])
            conn.execute("INSERT INTO canonical_id_redirects (redirect_id,redirect_type,from_id,to_id,source_table,target_table,created_at,updated_at) VALUES ('r1','x','a','b','target_gap_leads','target_gap_leads','now','now')")
            conn.execute("INSERT INTO canonical_id_redirects (redirect_id,redirect_type,from_id,to_id,source_table,target_table,created_at,updated_at) VALUES ('r2','x','b','a','target_gap_leads','target_gap_leads','now','now')")
            conn.commit()
        (tmp_path / "frontend_redirects.json").write_text("{}")
        summary = val.validate(db, tmp_path, tmp_path / "redirect.md")
        assert summary["status"] == "FAIL"
        assert "no_redirect_loops" in (tmp_path / "redirect.md").read_text()


def test_final_release_package_and_apply_dry_run_do_not_overwrite_public_data():
    pkg = load("release_package_test", "build_final_frontend_release_package.py")
    apply = load("release_apply_test", "apply_final_release_package.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for sub in ["map", "redirect", "coverage"]:
            (tmp_path / sub).mkdir()
        (tmp_path / "map" / "map_overlay_frontend_data.json").write_text(json.dumps({"metadata_place_overlay": [], "lead_place_overlay": []}))
        (tmp_path / "redirect" / "frontend_redirects.json").write_text("{}")
        (tmp_path / "coverage" / "release_coverage_1926_2011.csv").write_text("band,total_items\n1926-1939,1\n")
        (tmp_path / "coverage" / "release_coverage_by_layer.csv").write_text("layer,count\naccepted,1\n")
        summary = pkg.build(tmp_path / "test.sqlite", tmp_path / "map", tmp_path / "redirect", tmp_path / "coverage", tmp_path / "package", True)
        dry = apply.apply(tmp_path / "package", False)
        assert summary["out_dir"].endswith("package")
        assert (tmp_path / "package" / "release-disclaimer.md").exists()
        assert dry["changed_files"] == []


def test_final_release_audit_fails_when_metadata_marked_public_and_dashboard_reports_blocked():
    mig = load("release_layer_migrate_audit_test", "migrate_release_layers_v1.py")
    audit = load("final_release_audit_test", "final_release_audit.py")
    dash = load("final_release_dashboard_test", "build_final_release_dashboard.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO release_metadata_gap_items (release_item_id,public_record_status,created_at,updated_at) VALUES ('bad','public_record','now','now')")
            conn.commit()
        audit.ROOT = tmp_path
        dash_root_coverage = tmp_path / "data" / "processed" / "v2" / "release_coverage_1926_2011"
        coverage = dash_root_coverage
        coverage.mkdir(parents=True, exist_ok=True)
        (coverage / "hard_gap_report.csv").write_text("gap_type,band,state,observed_value,threshold,severity,explanation,requires_bounded_patch\n")
        map_dir = tmp_path / "data" / "processed" / "v2" / "final_map_layers"
        map_dir.mkdir(parents=True, exist_ok=True)
        (map_dir / "map_layer_counts.json").write_text(json.dumps({"accepted_public_map": 1, "metadata_place_overlay": 0, "lead_place_overlay": 0}))
        package = tmp_path / "package"
        package.mkdir()
        (package / "release-counts.json").write_text(json.dumps({"accepted_public_records": 1}))
        (package / "release-disclaimer.md").write_text("Metadata-only layer is not proof")
        redirects = tmp_path / "redirects"
        redirects.mkdir()
        (redirects / "redirect_validation_report.md").write_text("Status: `PASS`")
        summary = audit.audit(db, package, redirects, tmp_path / "audit")
        assert summary["status"] == "FAIL"
        d = dash.build(tmp_path / "audit", coverage, map_dir, redirects, tmp_path / "dashboard.md")
        assert d["status"] == "blocked"
        assert "inspect CSV" not in (tmp_path / "dashboard.md").read_text()
