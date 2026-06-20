"""Version 2 normalized narrative archive schema and controlled values."""

from __future__ import annotations


SCHEMA_VERSION = "2.0.0"

NARRATIVE_TYPES = {
    "encounter_account",
    "apparition_account",
    "ghost_legend",
    "rumour_account",
    "local_legend",
    "traditional_narrative",
    "spirit_person_narrative",
    "giant_or_ogre_narrative",
    "descriptive_belief_record",
    "retelling_or_adaptation",
}

SECONDARY_ROLES = {
    "heritage_discourse",
    "tourism_discourse",
    "media_commentary",
    "scholarly_commentary",
    "catalogue_metadata",
    "source_pointer",
    "unresolved_lead",
    "control",
    "exclusion",
}

DISPLAY_MODES = {"full", "summary_only", "metadata_only", "suppressed"}
ANALYSIS_STATUSES = {
    "display_ready_reviewed",
    "display_ready_unreviewed",
    "review_required",
    "lead_only",
    "excluded",
}

DATE_PRECISIONS = {
    "exact_day",
    "month",
    "year",
    "decade",
    "range",
    "circa",
    "before",
    "after",
    "unknown",
}

LOCATION_ROLES = {
    "alleged_event_location",
    "apparition_location",
    "narrative_setting",
    "legend_associated_place",
    "rumour_circulation_place",
    "cultural_association_region",
    "source_collection_location",
    "publication_location",
    "narrator_location",
    "uncertain_or_broad_location",
}

SOURCE_RELATIONSHIP_TYPES = {
    "first_known_attestation",
    "original_publication",
    "near_contemporary_report",
    "witness_account_publication",
    "syndicated_reprint",
    "reprint_with_variation",
    "archive_reproduction",
    "collector_transcription",
    "oral_history_publication",
    "translation",
    "retrospective_summary",
    "later_retelling",
    "adaptation",
    "tourism_retelling",
    "scholarly_commentary",
    "media_commentary",
    "catalogue_pointer",
    "derivative_web_summary",
}


V2_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL,
        checksum TEXT,
        reversible INTEGER DEFAULT 0,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_concepts (
        entity_concept_id INTEGER PRIMARY KEY,
        concept_key TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        concept_scope TEXT NOT NULL,
        description TEXT,
        sensitivity_level TEXT,
        not_species_note TEXT DEFAULT 'Analytical organization concept only; not a biological species.',
        created_at TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_items (
        source_item_id INTEGER PRIMARY KEY,
        legacy_record_id INTEGER UNIQUE,
        source_id INTEGER,
        external_id TEXT,
        title TEXT,
        publication_or_organisation TEXT,
        author_or_creator TEXT,
        publication_date_text TEXT,
        publication_date_start TEXT,
        publication_date_end TEXT,
        publication_date_precision TEXT,
        access_date TEXT,
        url TEXT,
        canonical_url TEXT,
        persistent_identifier TEXT,
        source_type TEXT,
        source_tier TEXT,
        source_mediation TEXT,
        publicness_status TEXT,
        rights_access_status TEXT,
        reproduction_status TEXT,
        raw_snapshot_path TEXT,
        raw_snapshot_sha256 TEXT,
        extracted_text_path TEXT,
        text_or_ocr_status TEXT,
        source_traceability_status TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (legacy_record_id) REFERENCES records(record_id),
        FOREIGN KEY (source_id) REFERENCES sources(source_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS narrative_units (
        narrative_id INTEGER PRIMARY KEY,
        migration_key TEXT UNIQUE,
        narrative_type TEXT,
        secondary_role TEXT,
        working_title TEXT,
        public_summary TEXT,
        narrative_status TEXT,
        analysis_status TEXT,
        humanoid_basis TEXT,
        australia_relation TEXT,
        earliest_attestation_start TEXT,
        earliest_attestation_end TEXT,
        earliest_attestation_precision TEXT,
        circulation_period_start TEXT,
        circulation_period_end TEXT,
        cultural_sensitivity TEXT,
        ethics_review_status TEXT,
        display_mode TEXT,
        normalized_entity_concept_id INTEGER,
        classification_confidence TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (normalized_entity_concept_id) REFERENCES entity_concepts(entity_concept_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS encounter_events (
        encounter_event_id INTEGER PRIMARY KEY,
        narrative_id INTEGER NOT NULL UNIQUE,
        event_date_start TEXT,
        event_date_end TEXT,
        event_date_precision TEXT,
        witness_count INTEGER,
        witness_type TEXT,
        encounter_context TEXT,
        morphology_evidence TEXT,
        behaviour_evidence TEXT,
        anomaly_evidence TEXT,
        event_summary TEXT,
        event_review_status TEXT,
        FOREIGN KEY (narrative_id) REFERENCES narrative_units(narrative_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_labels (
        entity_label_id INTEGER PRIMARY KEY,
        source_item_id INTEGER NOT NULL,
        narrative_id INTEGER,
        label_text TEXT NOT NULL,
        normalized_text TEXT,
        language_or_dialect TEXT,
        label_type TEXT,
        supplied_by TEXT,
        source_context TEXT,
        entity_concept_id INTEGER,
        normalization_status TEXT,
        review_status TEXT,
        FOREIGN KEY (source_item_id) REFERENCES source_items(source_item_id),
        FOREIGN KEY (narrative_id) REFERENCES narrative_units(narrative_id),
        FOREIGN KEY (entity_concept_id) REFERENCES entity_concepts(entity_concept_id),
        UNIQUE(source_item_id, narrative_id, label_text, label_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS narrative_source_links (
        narrative_source_link_id INTEGER PRIMARY KEY,
        narrative_id INTEGER NOT NULL,
        source_item_id INTEGER NOT NULL,
        relationship_type TEXT NOT NULL,
        confidence TEXT,
        evidence_note TEXT,
        human_review_status TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (narrative_id) REFERENCES narrative_units(narrative_id),
        FOREIGN KEY (source_item_id) REFERENCES source_items(source_item_id),
        UNIQUE(narrative_id, source_item_id, relationship_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS narrative_relations (
        narrative_relation_id INTEGER PRIMARY KEY,
        source_narrative_id INTEGER NOT NULL,
        target_narrative_id INTEGER NOT NULL,
        relationship_type TEXT NOT NULL,
        confidence TEXT,
        evidence_note TEXT,
        review_status TEXT,
        created_at TEXT,
        FOREIGN KEY (source_narrative_id) REFERENCES narrative_units(narrative_id),
        FOREIGN KEY (target_narrative_id) REFERENCES narrative_units(narrative_id),
        UNIQUE(source_narrative_id, target_narrative_id, relationship_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS narrative_locations (
        narrative_location_id INTEGER PRIMARY KEY,
        narrative_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        source_item_id INTEGER,
        location_role TEXT NOT NULL,
        location_text_as_printed TEXT,
        location_precision TEXT,
        verification_status TEXT,
        confidence TEXT,
        evidence_excerpt TEXT,
        review_status TEXT,
        created_at TEXT,
        FOREIGN KEY (narrative_id) REFERENCES narrative_units(narrative_id),
        FOREIGN KEY (location_id) REFERENCES locations(location_id),
        FOREIGN KEY (source_item_id) REFERENCES source_items(source_item_id),
        UNIQUE(narrative_id, location_id, source_item_id, location_role)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reviews (
        review_id INTEGER PRIMARY KEY,
        review_type TEXT NOT NULL,
        subject_table TEXT NOT NULL,
        subject_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        reviewer TEXT,
        reviewed_at TEXT,
        notes TEXT,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS leads (
        lead_id INTEGER PRIMARY KEY,
        run_id TEXT,
        source_id INTEGER,
        source_name TEXT,
        source_type TEXT,
        title TEXT,
        url TEXT,
        external_id TEXT,
        query_string TEXT,
        lead_type TEXT,
        lead_status TEXT,
        reason_not_accepted TEXT,
        notes TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (source_id) REFERENCES sources(source_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exclusions (
        exclusion_id INTEGER PRIMARY KEY,
        legacy_record_id INTEGER,
        source_item_id INTEGER,
        narrative_id INTEGER,
        exclusion_type TEXT NOT NULL,
        reason TEXT NOT NULL,
        evidence_note TEXT,
        created_at TEXT,
        FOREIGN KEY (legacy_record_id) REFERENCES records(record_id),
        FOREIGN KEY (source_item_id) REFERENCES source_items(source_item_id),
        FOREIGN KEY (narrative_id) REFERENCES narrative_units(narrative_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS legacy_record_mappings (
        legacy_record_id INTEGER PRIMARY KEY,
        source_item_id INTEGER NOT NULL,
        narrative_id INTEGER,
        primary_record_role TEXT NOT NULL,
        migration_status TEXT NOT NULL,
        migration_confidence TEXT,
        review_flags TEXT,
        migration_notes TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (legacy_record_id) REFERENCES records(record_id),
        FOREIGN KEY (source_item_id) REFERENCES source_items(source_item_id),
        FOREIGN KEY (narrative_id) REFERENCES narrative_units(narrative_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collection_candidates_v2 (
        candidate_id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL,
        candidate_status TEXT NOT NULL,
        source_name TEXT,
        source_type TEXT,
        source_tier TEXT,
        title TEXT,
        publication_or_organisation TEXT,
        publication_date_text TEXT,
        url TEXT,
        canonical_url TEXT,
        external_id TEXT,
        narrative_type TEXT,
        secondary_role TEXT,
        australian_relation TEXT,
        humanoid_basis TEXT,
        source_label TEXT,
        location_text TEXT,
        location_role TEXT,
        ethics_review_status TEXT,
        cultural_sensitivity TEXT,
        acceptance_decision TEXT,
        rejection_reason TEXT,
        evidence_summary TEXT,
        raw_metadata_json TEXT,
        created_at TEXT,
        updated_at TEXT,
        UNIQUE(run_id, canonical_url, external_id)
    )
    """,
]

V2_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_source_items_legacy ON source_items(legacy_record_id)",
    "CREATE INDEX IF NOT EXISTS idx_source_items_canonical_url ON source_items(canonical_url)",
    "CREATE INDEX IF NOT EXISTS idx_source_items_external_id ON source_items(external_id)",
    "CREATE INDEX IF NOT EXISTS idx_source_items_source_type ON source_items(source_type)",
    "CREATE INDEX IF NOT EXISTS idx_narrative_units_type ON narrative_units(narrative_type)",
    "CREATE INDEX IF NOT EXISTS idx_narrative_units_status ON narrative_units(analysis_status)",
    "CREATE INDEX IF NOT EXISTS idx_entity_labels_text ON entity_labels(normalized_text)",
    "CREATE INDEX IF NOT EXISTS idx_narrative_locations_role ON narrative_locations(location_role)",
    "CREATE INDEX IF NOT EXISTS idx_collection_candidates_status ON collection_candidates_v2(candidate_status)",
]

V2_TABLES = [
    "schema_migrations",
    "entity_concepts",
    "source_items",
    "narrative_units",
    "encounter_events",
    "entity_labels",
    "narrative_source_links",
    "narrative_relations",
    "narrative_locations",
    "reviews",
    "leads",
    "exclusions",
    "legacy_record_mappings",
    "collection_candidates_v2",
]
