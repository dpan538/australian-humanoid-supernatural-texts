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


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def minimal_release_inputs(tmp_path: Path):
    db = tmp_path / "test.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE canonical_id_redirects (redirect_id TEXT, from_id TEXT, to_id TEXT, active INTEGER)")
        conn.execute("CREATE TABLE canonical_url_redirects (redirect_id TEXT, from_url TEXT, to_url TEXT, url_role TEXT, active INTEGER)")
        conn.executemany("INSERT INTO canonical_id_redirects VALUES (?,?,?,1)", [("r1", "old", "new")])
        conn.executemany("INSERT INTO canonical_url_redirects VALUES (?,?,?,?,1)", [("u1", "https://old", "https://new", "source_url")])
        conn.commit()
    frontend = tmp_path / "public/data/frontend-data.json"
    write_json(frontend, {"summary": {"record_count": 4265, "mapped_record_count": 1593}, "records": [], "map_flags": []})
    package = tmp_path / "package"
    package.mkdir()
    write_json(package / "release-counts.json", {"accepted_public_records": 4265, "metadata_overlay": 1552, "lead_overlay": 1448})
    for name in ["frontend-data.release-candidate.json", "frontend-map-overlays.release-candidate.json", "frontend-redirects.release-candidate.json", "release-coverage.release-candidate.json", "source-intelligence.release-candidate.json"]:
        write_json(package / name, {})
    (package / "release-disclaimer.md").write_text("Metadata-only layer is not proof", encoding="utf-8")
    coverage = tmp_path / "coverage"
    coverage.mkdir()
    (coverage / "release_coverage_1926_2011.csv").write_text("band,total_items\n1926-1939,37964\n", encoding="utf-8")
    (coverage / "hard_gap_report.csv").write_text("gap_type,band\n", encoding="utf-8")
    (coverage / "release_coverage_by_decade.csv").write_text("decade,count\n1950s,1\n", encoding="utf-8")
    (coverage / "release_coverage_by_state.csv").write_text("state,count\nWA,1\n", encoding="utf-8")
    (coverage / "release_coverage_by_layer.csv").write_text("layer,count\nmetadata_only_gap_layer,1552\n", encoding="utf-8")
    map_dir = tmp_path / "map"
    write_json(map_dir / "map_layer_counts.json", {"accepted_public_map": 1593, "metadata_place_overlay": 1552, "lead_place_overlay": 1448})
    redirect = tmp_path / "redirect"
    redirect.mkdir()
    (redirect / "canonical_id_redirects.csv").write_text("redirect_id,from_id,to_id\nr1,old,new\n", encoding="utf-8")
    (redirect / "canonical_url_redirects.csv").write_text("redirect_id,from_url,to_url,url_role\nu1,https://old,https://new,source_url\n", encoding="utf-8")
    return db, frontend, package, coverage, map_dir, redirect


def test_frontend_count_contract_separates_layers_and_map_count():
    mod = load("frontend_count_contract_test", "build_frontend_count_contract.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db, frontend, package, coverage, map_dir, redirect = minimal_release_inputs(tmp_path)
        contract = mod.build_contract(db, frontend, package, coverage, map_dir, redirect, tmp_path / "contract.json", tmp_path / "report.md", True)
        assert contract["counts"]["accepted_public_map_points"] == 1593
        assert contract["counts"]["metadata_gap_items"] == 1552
        assert contract["counts"]["lead_overlay_items"] == 1448
        assert contract["counts"]["critical_hard_gaps_1926_2011"] == 0
        assert contract["rules"]["metadata_items_are_public_records"] is False


def test_frontend_display_audit_detects_stale_counts_labels_and_imports():
    mod = load("frontend_display_audit_test", "audit_frontend_display_contract.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_json(tmp_path / "public/data/release-count-contract.json", {"counts": {"accepted_public_map_points": 1593}})
        page = tmp_path / "app/page.tsx"
        page.parent.mkdir(parents=True)
        page.write_text('const old = "4,393 records"; const bad = "research leads are public records"; import x from "/data/frontend-data.experimental-4000.json";', encoding="utf-8")
        result = mod.audit(tmp_path, tmp_path / "public/data/release-count-contract.json", tmp_path / "out")
        assert result["hardcoded_count_hits"] >= 1
        assert result["stale_data_imports"] >= 1
        assert result["label_misuse"] >= 1


def test_integrate_release_sidecars_creates_loader_and_fallbacks():
    mod = load("integrate_sidecars_test", "integrate_release_sidecars_into_frontend.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        package = tmp_path / "package"
        package.mkdir()
        for name in mod.SIDECAR_FILES:
            (package / name).write_text("{}" if name.endswith(".json") else "disclaimer", encoding="utf-8")
        write_json(tmp_path / "public/data/release-count-contract.json", {"counts": {}})
        (tmp_path / "components").mkdir()
        (tmp_path / "components/archive-terminal.tsx").write_text("ReleaseLayerStrip loadReleaseSiteData ReleaseMapOverlayPanel", encoding="utf-8")
        (tmp_path / "components/source").mkdir(parents=True)
        (tmp_path / "components/source/source-view.tsx").write_text("ReleaseSiteData RESEARCH LAYERS", encoding="utf-8")
        (tmp_path / "app/about").mkdir(parents=True)
        (tmp_path / "app/about/page.tsx").write_text("loadReleaseContractForAbout Metadata-only gap items", encoding="utf-8")
        result = mod.integrate(tmp_path, package, tmp_path / "public/data/release-count-contract.json", True)
        loader = (tmp_path / "lib/release-data.ts").read_text(encoding="utf-8")
        assert "loadAcceptedFrontendData" in loader
        assert "loadMapOverlays" in loader
        assert result["files_modified"] == 1


def test_release_cards_have_caveats_and_redirects():
    mod = load("release_cards_test", "generate_release_cards.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.ROOT = tmp_path
        write_json(tmp_path / "public/data/frontend-data.json", {"summary": {"record_count": 1}, "records": [{"record_id": 1, "title": "Accepted", "year": 1930, "source_name": "Source", "has_strict_map_point": True}]})
        db = tmp_path / "test.sqlite"
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE release_metadata_gap_items (release_item_id TEXT, title TEXT, source_name TEXT, source_family TEXT, inferred_year INTEGER, target_state TEXT, url TEXT, map_display_status TEXT)")
            conn.execute("CREATE TABLE release_lead_overlay_items (release_lead_id TEXT, title TEXT, source_name TEXT, source_family TEXT, inferred_year INTEGER, target_state TEXT, url TEXT, blocker TEXT, evidence_gap TEXT, map_display_status TEXT)")
            conn.execute("INSERT INTO release_metadata_gap_items VALUES ('m1','Meta','S','state_library_catalogue',1955,'WA','https://old','not_public_map')")
            conn.execute("INSERT INTO release_lead_overlay_items VALUES ('l1','Lead','S','heritage_register',1960,'SA','https://lead','','missing_date','not_public_map')")
            conn.commit()
        redirect = tmp_path / "redirect"
        redirect.mkdir()
        (redirect / "canonical_url_redirects.csv").write_text("from_url,to_url\nhttps://old,https://new\n", encoding="utf-8")
        (redirect / "canonical_id_redirects.csv").write_text("redirect_id,from_id,to_id,reason,source_table\nr1,old,new,duplicate,target_gap_leads\n", encoding="utf-8")
        result = mod.generate(db, tmp_path / "package", redirect, tmp_path / "release-cards.json", tmp_path / "release_cards_report.md", True)
        cards = json.loads((tmp_path / "release-cards.json").read_text())["cards"]
        assert result["metadata_gap_card"] == 1
        assert any(card["card_type"] == "metadata_gap_card" and "not an accepted public record" in card["caveat"] for card in cards)
        assert any(card["card_type"] == "lead_overlay_card" and card["public_record_status"] == "not_public_record" for card in cards)
        assert any(card["card_type"] == "redirect_notice_card" and card["redirect_target"] == "new" for card in cards)


def test_release_charts_match_count_contract_and_separate_layers():
    mod = load("release_charts_test", "build_release_chart_data.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db, frontend, package, coverage, map_dir, redirect = minimal_release_inputs(tmp_path)
        contract = tmp_path / "contract.json"
        write_json(contract, {"counts": {"accepted_public_map_points": 1593, "metadata_gap_items": 1552, "lead_overlay_items": 1448, "id_redirects": 1, "url_redirects": 1}})
        result = mod.build_charts(db, contract, coverage, map_dir, package, tmp_path / "charts.json", tmp_path / "charts.md", True)
        charts = json.loads((tmp_path / "charts.json").read_text())["charts"]
        assert result["charts"] == 10
        assert all(chart["layer_definitions"] for chart in charts)
        assert any(chart["title"].startswith("Accepted map") for chart in charts)


def test_frontend_release_contract_validation_fails_duplicate_card_ids():
    mod = load("frontend_release_validation_test", "validate_frontend_release_contracts.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_json(tmp_path / "contract.json", {"counts": {"accepted_public_map_points": 1593}, "rules": {"metadata_items_are_public_records": False, "lead_items_are_public_records": False}})
        write_json(tmp_path / "cards.json", {"cards": [{"id": "x", "layer_type": "research_lead", "caveat": "Research lead", "public_record_status": "not_public_record"}, {"id": "x", "layer_type": "research_lead", "caveat": "Research lead", "public_record_status": "not_public_record"}]})
        write_json(tmp_path / "charts.json", {"contract_counts": {"accepted_public_map_points": 1593}, "charts": [{"title": str(i), "caveat": "c", "source_file_provenance": ["p"]} for i in range(10)]})
        package = tmp_path / "package"
        package.mkdir()
        for name in mod.SIDECAR_FILES:
            (package / name).write_text("{}" if name.endswith(".json") else "d", encoding="utf-8")
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib/release-data.ts").write_text("loadReleaseCountContract loadMapOverlays loadReleaseCoverage loadRedirects release-count-contract", encoding="utf-8")
        (tmp_path / "components").mkdir()
        (tmp_path / "components/x.tsx").write_text("ReleaseLayerStrip", encoding="utf-8")
        try:
            mod.validate(tmp_path, tmp_path / "contract.json", tmp_path / "cards.json", tmp_path / "charts.json", package, tmp_path / "out.md")
            assert False
        except SystemExit:
            assert "duplicate card IDs" in (tmp_path / "out.md").read_text(encoding="utf-8")


def test_frontend_smoke_reports_build_failure():
    mod = load("frontend_smoke_test", "run_frontend_smoke_tests.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_json(tmp_path / "package.json", {"scripts": {"build": "node -e \"process.exit(1)\""}})
        write_json(tmp_path / "public/data/release-count-contract.json", {"counts": {"accepted_public_map_points": 1593}})
        try:
            mod.smoke(tmp_path, tmp_path / "smoke", True)
            assert False
        except SystemExit:
            assert "Status: `FAIL`" in (tmp_path / "smoke/frontend_smoke_test_report.md").read_text(encoding="utf-8")


def test_post_release_site_audit_fails_map_drift():
    mod = load("post_release_site_audit_test", "post_release_site_audit.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_json(tmp_path / "contract.json", {"counts": {"accepted_public_records": 1, "accepted_public_map_points": 2, "metadata_gap_items": 0, "lead_overlay_items": 0}, "rules": {"metadata_items_are_public_records": False, "lead_items_are_public_records": False}})
        write_json(tmp_path / "cards.json", {"cards": []})
        write_json(tmp_path / "charts.json", {"charts": []})
        final = tmp_path / "final"
        final.mkdir()
        (final / "final_release_go_no_go.md").write_text("Status: `ready`", encoding="utf-8")
        package = tmp_path / "data/processed/v2/final_release_package"
        package.mkdir(parents=True)
        (package / "final_release_apply_report.md").write_text("Database mutated: `no`\nAccepted records DB tables changed: `no`\nPublic map flags changed: `no`", encoding="utf-8")
        (tmp_path / "data/processed/v2/post_release_site_integration/frontend_release_contract_validation.md").parent.mkdir(parents=True)
        (tmp_path / "data/processed/v2/post_release_site_integration/frontend_release_contract_validation.md").write_text("Status: `PASS`", encoding="utf-8")
        (tmp_path / "data/processed/v2/post_release_site_integration/smoke_tests").mkdir(parents=True)
        (tmp_path / "data/processed/v2/post_release_site_integration/smoke_tests/frontend_smoke_test_report.md").write_text("Status: `PASS`", encoding="utf-8")
        (tmp_path / "data/processed/v2/post_release_site_integration/frontend_display_audit").mkdir(parents=True)
        (tmp_path / "data/processed/v2/post_release_site_integration/frontend_display_audit/frontend_display_audit.md").write_text("Status: `PASS`", encoding="utf-8")
        try:
            mod.audit(tmp_path, tmp_path / "db.sqlite", tmp_path / "contract.json", tmp_path / "cards.json", tmp_path / "charts.json", final, tmp_path / "audit", True)
            assert False
        except SystemExit:
            assert "accepted_public_map_count" in (tmp_path / "audit/post_release_go_no_go.md").read_text(encoding="utf-8")


def test_major_phase_report_contains_sections_counts_and_limitations():
    mod = load("major_phase_report_test", "build_major_phase_report.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_json(tmp_path / "public/data/release-count-contract.json", {"counts": {"accepted_public_map_points": 1593, "metadata_gap_items": 1552, "lead_overlay_items": 1448, "coverage_items_1926_2011": 37964, "critical_hard_gaps_1926_2011": 0, "display_hard_gaps_1926_2011": 0, "id_redirects": 8697, "url_redirects": 9876}})
        (tmp_path / "data/processed/v2/post_release_site_integration/final_site_audit").mkdir(parents=True)
        (tmp_path / "data/processed/v2/post_release_site_integration/final_site_audit/post_release_go_no_go.md").write_text("Status: `ready`", encoding="utf-8")
        mod.report(tmp_path, tmp_path / "db.sqlite", tmp_path / "MAJOR.md", tmp_path / "also.md", True)
        text = (tmp_path / "MAJOR.md").read_text(encoding="utf-8")
        assert "Executive Summary" in text
        assert "Data-Layer Architecture" in text
        assert "37,964" in text
        assert "Known Limitations" in text
        assert "thousands of rows" not in text
