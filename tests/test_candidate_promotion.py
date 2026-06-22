import importlib.util
import sys
import tempfile
from pathlib import Path

from aus_humanoid.db import connect, initialise_database


ROOT = Path(__file__).resolve().parents[1]


def load_promoter():
    path = ROOT / "scripts" / "promote_accepted_candidates.py"
    spec = importlib.util.spec_from_file_location("promote_accepted_candidates", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.promote_candidates


def seed_candidate(db_path: Path) -> None:
    with connect(db_path) as conn:
        from aus_humanoid.v2_schema import V2_INDEX_STATEMENTS, V2_SCHEMA_STATEMENTS

        for statement in V2_SCHEMA_STATEMENTS:
            conn.execute(statement)
        for statement in V2_INDEX_STATEMENTS:
            conn.execute(statement)
        conn.execute(
            """
            INSERT INTO collection_candidates_v2(
                candidate_id, run_id, candidate_status, source_name, source_type,
                source_tier, title, publication_or_organisation,
                publication_date_text, access_date, url, canonical_url, external_id,
                publicness_status, rights_access_status, narrative_type,
                secondary_role, australian_relation, humanoid_basis, source_label,
                location_text, location_role, latitude, longitude,
                location_precision, geocode_source, geocode_verification_status,
                coordinate_evidence_note, duplicate_check_status, quality_class,
                ethics_review_status, cultural_sensitivity, acceptance_decision,
                evidence_summary
            )
            VALUES (
                1, 'test_run', 'accepted', 'Test Archive', 'institutional_web',
                'A', 'Test ghost at the old hall', 'Test Archive',
                '1901', '2026-06-22', 'https://example.org/item/1',
                'https://example.org/item/1', 'test:item:1',
                'public', 'public page', 'ghost_legend',
                'heritage_discourse', 'australia_public_text', 'person_form_apparition',
                'ghost', 'Example Town', 'legend_associated_place',
                -35.2, 149.1, 'town', 'manual_gazetteer',
                'verified_place', 'The public item names Example Town.',
                'not_duplicate', 'A', 'public_context_ok', 'low', 'accepted',
                'The public archive item describes a person-form ghost legend at the old hall.'
            )
            """
        )
        conn.commit()


def test_accepted_candidate_promotes_to_canonical_record_idempotently():
    promote_candidates = load_promoter()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.sqlite"
        initialise_database(db_path)
        seed_candidate(db_path)

        first = promote_candidates(db_path)
        second = promote_candidates(db_path)

        with connect(db_path) as conn:
            assert first["promoted"] == 1
            assert second["promoted"] == 0
            assert conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM collection_candidate_record_mappings").fetchone()[0] == 1
            mapping = conn.execute("SELECT record_id FROM collection_candidate_record_mappings WHERE candidate_id = 1").fetchone()
            assert mapping is not None
            assert conn.execute("SELECT COUNT(*) FROM source_items WHERE legacy_record_id = ?", (mapping["record_id"],)).fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM coding WHERE record_id = ?", (mapping["record_id"],)).fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM record_locations WHERE record_id = ?", (mapping["record_id"],)).fetchone()[0] == 1
