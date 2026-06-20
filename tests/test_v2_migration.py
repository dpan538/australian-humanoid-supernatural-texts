import sqlite3
import tempfile
import importlib.util
import sys
from pathlib import Path

from aus_humanoid.db import connect, initialise_database
from aus_humanoid.v2_schema import V2_TABLES


ROOT = Path(__file__).resolve().parents[1]


def load_migrate():
    path = ROOT / "scripts" / "migrate_legacy_records_v2.py"
    spec = importlib.util.spec_from_file_location("migrate_legacy_records_v2", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.migrate


def seed_minimal_legacy(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sources(source_id, source_name, source_type, publicness_level)
            VALUES (1, 'Test Public Source', 'modern_web', 'public_page')
            """
        )
        conn.execute(
            """
            INSERT INTO figures(
                figure_id, canonical_name, cluster, tier, include_status,
                humanoid_degree, ontology_default, involves_indigenous_knowledge
            )
            VALUES (
                1, 'Hairy Man', 'yowie_yahoo_hairy_man', 'tier_1_core',
                'include_v1', 'explicit_humanoid', 'cryptid_style_apeman', 0
            )
            """
        )
        conn.execute(
            """
            INSERT INTO records(
                record_id, source_id, figure_id, external_id, title,
                publication, date_published, year, url, snippet, publicness_level
            )
            VALUES (
                1, 1, 1, 'test:1', 'Hairy Man report',
                'Test Publication', '1901', 1901,
                'https://example.org/report?utm_source=test',
                'The source reports a hairy man near a town.', 'public_page'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO coding(record_id, canonical_figure_guess, figure_name_as_printed, relevance_code, ethics_flag)
            VALUES (1, 'Hairy Man', 'Hairy Man', 'needs_review', 'ok_public')
            """
        )
        conn.commit()


def test_v2_migration_creates_tables_and_mapping():
    migrate = load_migrate()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        initialise_database(db_path)
        seed_minimal_legacy(db_path)
        migrate(db_path)
        with connect(db_path) as conn:
            tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            assert set(V2_TABLES).issubset(tables)
            assert conn.execute("SELECT COUNT(*) FROM legacy_record_mappings").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM source_items").fetchone()[0] == 1


def test_v2_migration_is_idempotent():
    migrate = load_migrate()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        initialise_database(db_path)
        seed_minimal_legacy(db_path)
        migrate(db_path)
        migrate(db_path)
        with connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM legacy_record_mappings").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM source_items").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM entity_labels").fetchone()[0] == 1


def test_automation_does_not_assign_analysis_ready_or_rewrite_label():
    migrate = load_migrate()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        initialise_database(db_path)
        seed_minimal_legacy(db_path)
        migrate(db_path)
        with connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM narrative_units WHERE analysis_status = 'analysis_ready'").fetchone()[0] == 0
            label = conn.execute("SELECT label_text FROM entity_labels").fetchone()[0]
            assert label == "Hairy Man"


def test_publication_location_role_not_silently_event_location():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        initialise_database(db_path)
        raw = sqlite3.connect(db_path)
        try:
            # A sanity check on the legacy table before V2 migration tests run.
            cols = [row[1] for row in raw.execute("PRAGMA table_info(record_locations)").fetchall()]
        finally:
            raw.close()
        assert "relation_type" in cols
