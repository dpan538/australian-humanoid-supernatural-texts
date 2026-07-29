import csv
import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "noauth_probe_open_routes.py"
    spec = importlib.util.spec_from_file_location("noauth_probe_open_routes", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_plan(path: Path, rows: list[dict[str, str]]):
    fieldnames = [
        "query_id", "route_id", "source_id", "source_name", "official_url", "state",
        "route_family", "source_tier", "collection_mode", "probe_mode", "time_band",
        "start_year", "end_year", "target_state", "target_locality", "term_family",
        "term", "query_string", "search_url", "should_fetch", "should_download_pdf",
        "should_extract_pdf_text", "ethics_risk", "sample_weight", "sample_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def base_row(**overrides):
    row = {
        "query_id": "q1",
        "route_id": "wa_history",
        "source_id": "wa_history",
        "source_name": "WA History",
        "official_url": "https://example.test/",
        "state": "WA",
        "route_family": "local_history_serial",
        "source_tier": "B",
        "collection_mode": "static_html_metadata",
        "probe_mode": "static_html",
        "time_band": "1955_1964",
        "start_year": "1955",
        "end_year": "1964",
        "target_state": "WA",
        "target_locality": "Perth",
        "term_family": "apparition_ghost",
        "term": "ghost",
        "query_string": "ghost Perth 1955 1964",
        "search_url": "https://example.test/search?q=ghost",
        "should_fetch": "true",
        "should_download_pdf": "false",
        "should_extract_pdf_text": "false",
    }
    row.update(overrides)
    return row


def isolate_outputs(mod, base: Path):
    original = (mod.REPORT_DIR, mod.DISCOVERY_DIR, mod.REVIEW_DIR)
    mod.REPORT_DIR = base / "processed"
    mod.DISCOVERY_DIR = base / "discovery"
    mod.REVIEW_DIR = base / "review"
    return original


def load_migration(name="migrate_collection_expansion_v2"):
    migrate_path = ROOT / "scripts" / "migrate_collection_expansion_v2.py"
    spec = importlib.util.spec_from_file_location(name, migrate_path)
    migrate = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = migrate
    spec.loader.exec_module(migrate)
    return migrate


def test_dry_run_stages_no_db_candidates():
    mod = load_module()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        db = base / "test.sqlite"
        plan = base / "plan.csv"
        write_plan(plan, [base_row()])
        original_dirs = isolate_outputs(mod, base)
        try:
            summary = mod.run_probe(db, plan, "dry", 10, execute=False)
        finally:
            mod.REPORT_DIR, mod.DISCOVERY_DIR, mod.REVIEW_DIR = original_dirs
        assert summary["candidates"] == 0
        assert not db.exists()
        assert "TROVE_API_KEY" not in Path(mod.__file__).read_text(encoding="utf-8")


def test_execute_stages_allowed_metadata_candidate():
    mod = load_module()
    migrate = load_migration()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        db = base / "test.sqlite"
        migrate.migrate(db)
        plan = base / "plan.csv"
        write_plan(plan, [base_row()])
        original_dirs = isolate_outputs(mod, base)
        original_allowed = mod.allowed_by_robots
        original_fetch = mod.fetch_html_safe
        try:
            mod.allowed_by_robots = lambda *_args, **_kwargs: True
            mod.fetch_html_safe = lambda *_args, **_kwargs: "<html><title>Perth ghost 1960</title><a href='/record'>Perth ghost archive 1960</a></html>"
            summary = mod.run_probe(db, plan, "exec", 10, execute=True)
        finally:
            mod.allowed_by_robots = original_allowed
            mod.fetch_html_safe = original_fetch
            mod.REPORT_DIR, mod.DISCOVERY_DIR, mod.REVIEW_DIR = original_dirs
        assert summary["staged"] == 1
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM collection_candidates").fetchone()[0] == 1


def test_discovery_route_and_pdf_body_are_skipped():
    mod = load_module()
    migrate = load_migration("migrate_collection_expansion_v2_skip")
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        db = base / "test.sqlite"
        migrate.migrate(db)
        plan = base / "plan.csv"
        write_plan(
            plan,
            [
                base_row(collection_mode="discovery_only"),
                base_row(query_id="q2", should_download_pdf="true", route_id="pdf_route"),
            ],
        )
        original_dirs = isolate_outputs(mod, base)
        try:
            summary = mod.run_probe(db, plan, "safe", 10, execute=True)
        finally:
            mod.REPORT_DIR, mod.DISCOVERY_DIR, mod.REVIEW_DIR = original_dirs
        assert summary["candidates"] == 0
        assert summary["policy_skipped"] >= 1
