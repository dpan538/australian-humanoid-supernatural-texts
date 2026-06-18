"""SQLite schema definitions for the project database."""

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS sources (
        source_id INTEGER PRIMARY KEY,
        source_name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        base_url TEXT,
        access_method TEXT,
        publicness_level TEXT,
        ethics_notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS figures (
        figure_id INTEGER PRIMARY KEY,
        canonical_name TEXT NOT NULL UNIQUE,
        cluster TEXT NOT NULL,
        tier TEXT NOT NULL,
        include_status TEXT NOT NULL,
        humanoid_degree TEXT,
        ontology_default TEXT,
        involves_indigenous_knowledge INTEGER DEFAULT 0,
        sensitivity_notes TEXT,
        description TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS aliases (
        alias_id INTEGER PRIMARY KEY,
        figure_id INTEGER NOT NULL,
        alias TEXT NOT NULL,
        alias_type TEXT NOT NULL,
        search_priority INTEGER DEFAULT 0,
        notes TEXT,
        FOREIGN KEY (figure_id) REFERENCES figures(figure_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS queries (
        query_id INTEGER PRIMARY KEY,
        figure_id INTEGER,
        source_id INTEGER NOT NULL,
        query_string TEXT NOT NULL,
        query_type TEXT NOT NULL,
        date_start TEXT,
        date_end TEXT,
        expected_noise_level TEXT,
        status TEXT DEFAULT 'planned',
        notes TEXT,
        FOREIGN KEY (figure_id) REFERENCES figures(figure_id),
        FOREIGN KEY (source_id) REFERENCES sources(source_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS records (
        record_id INTEGER PRIMARY KEY,
        source_id INTEGER NOT NULL,
        query_id INTEGER,
        figure_id INTEGER,
        external_id TEXT,
        title TEXT,
        publication TEXT,
        author TEXT,
        date_published TEXT,
        year INTEGER,
        url TEXT,
        snippet TEXT,
        full_text_path TEXT,
        raw_metadata_json TEXT,
        access_status TEXT,
        publicness_level TEXT,
        ingestion_status TEXT DEFAULT 'raw',
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (source_id) REFERENCES sources(source_id),
        FOREIGN KEY (query_id) REFERENCES queries(query_id),
        FOREIGN KEY (figure_id) REFERENCES figures(figure_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS record_alias_matches (
        match_id INTEGER PRIMARY KEY,
        record_id INTEGER NOT NULL,
        alias_id INTEGER NOT NULL,
        matched_text TEXT,
        match_context TEXT,
        confidence TEXT,
        FOREIGN KEY (record_id) REFERENCES records(record_id),
        FOREIGN KEY (alias_id) REFERENCES aliases(alias_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS coding (
        coding_id INTEGER PRIMARY KEY,
        record_id INTEGER NOT NULL UNIQUE,
        canonical_figure_guess TEXT,
        figure_name_as_printed TEXT,
        variant_normalisation TEXT,
        ontology_code TEXT,
        humanoid_degree_code TEXT,
        source_voice TEXT,
        genre TEXT,
        publicness_code TEXT,
        relevance_code TEXT,
        ethics_flag TEXT,
        notes TEXT,
        coded_by TEXT DEFAULT 'system_seed',
        coded_at TEXT,
        FOREIGN KEY (record_id) REFERENCES records(record_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dedupe_groups (
        dedupe_group_id INTEGER PRIMARY KEY,
        group_key TEXT UNIQUE,
        canonical_record_id INTEGER,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS record_dedupe (
        record_id INTEGER NOT NULL,
        dedupe_group_id INTEGER NOT NULL,
        duplicate_type TEXT,
        similarity_score REAL,
        PRIMARY KEY(record_id, dedupe_group_id),
        FOREIGN KEY (record_id) REFERENCES records(record_id),
        FOREIGN KEY (dedupe_group_id) REFERENCES dedupe_groups(dedupe_group_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attention_series (
        attention_id INTEGER PRIMARY KEY,
        figure_id INTEGER,
        source_id INTEGER NOT NULL,
        term TEXT NOT NULL,
        date TEXT NOT NULL,
        value REAL,
        geo TEXT,
        metric_type TEXT,
        notes TEXT,
        FOREIGN KEY (figure_id) REFERENCES figures(figure_id),
        FOREIGN KEY (source_id) REFERENCES sources(source_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS locations (
        location_id INTEGER PRIMARY KEY,
        place_name TEXT NOT NULL UNIQUE,
        region TEXT,
        state_territory TEXT,
        country TEXT DEFAULT 'Australia',
        latitude REAL,
        longitude REAL,
        location_type TEXT,
        geocode_source TEXT,
        verification_status TEXT,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS record_locations (
        record_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        relation_type TEXT,
        evidence_text TEXT,
        confidence TEXT,
        notes TEXT,
        PRIMARY KEY(record_id, location_id, relation_type),
        FOREIGN KEY (record_id) REFERENCES records(record_id),
        FOREIGN KEY (location_id) REFERENCES locations(location_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collection_runs (
        collection_run_id INTEGER PRIMARY KEY,
        run_name TEXT NOT NULL,
        run_started_at TEXT,
        run_finished_at TEXT,
        scope_notes TEXT,
        methods TEXT,
        limitations TEXT
    )
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_records_year ON records(year)",
    "CREATE INDEX IF NOT EXISTS idx_figures_canonical_name ON figures(canonical_name)",
    "CREATE INDEX IF NOT EXISTS idx_aliases_alias ON aliases(alias)",
    "CREATE INDEX IF NOT EXISTS idx_sources_source_type ON sources(source_type)",
    "CREATE INDEX IF NOT EXISTS idx_queries_query_string ON queries(query_string)",
    "CREATE INDEX IF NOT EXISTS idx_records_url ON records(url)",
    "CREATE INDEX IF NOT EXISTS idx_records_external_id ON records(external_id)",
    "CREATE INDEX IF NOT EXISTS idx_queries_source_date ON queries(source_id, date_start, date_end)",
    "CREATE INDEX IF NOT EXISTS idx_records_source ON records(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_attention_term_date ON attention_series(term, date)",
    "CREATE INDEX IF NOT EXISTS idx_locations_place ON locations(place_name)",
    "CREATE INDEX IF NOT EXISTS idx_locations_region ON locations(region, state_territory)",
    "CREATE INDEX IF NOT EXISTS idx_record_locations_record ON record_locations(record_id)",
]

REQUIRED_TABLES = [
    "sources",
    "figures",
    "aliases",
    "queries",
    "records",
    "record_alias_matches",
    "coding",
    "dedupe_groups",
    "record_dedupe",
    "attention_series",
    "locations",
    "record_locations",
    "collection_runs",
]
