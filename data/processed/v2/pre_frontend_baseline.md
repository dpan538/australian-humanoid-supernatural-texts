# Pre-Frontend Baseline

- Active database: `data/processed/australian_humanoid_figures.sqlite`
- Active database size: `30851072` bytes
- Active database SHA256: `2be10510d14b826f7042b15dc0d512f68469b1132f82bac69a4d0823d0b8028b`
- SQLite schema version: `62`
- Frontend JSON: `public/data/frontend-data.json`
- Frontend JSON SHA256: `55f8e65ea145438dfaf06bc59ead24f2375ec61c5eb4abbe5e2781355b25c58c`
- Snapshot: `data/releases/pre_frontend_optimization_20260622T073320Z`

## Counts
- total_canonical_records_sqlite: `2410`
- public_export_records: `2397`
- suppressed_records: `13`
- context_records_estimated: `35`
- first_class_records_estimated: `2362`
- rejected_or_excluded_rows_estimated: `122`
- promoted_candidates: `1313`
- unpromoted_accepted_candidates: `0`
- source_items: `2298`
- narrative_units: `2229`
- source_organisations: `34`
- source_families: `21`
- mapped_public_records: `921`
- map_points_length: `921`
- map_flags_length: `921`
- unmapped_public_records: `1476`

## Invariants
- mapped_public_records_equals_map_lengths: `True`
- every_map_flag_references_public_record: `True`
- public_record_ids_unique: `True`
- map_record_ids_unique: `True`
- suppressed_or_restricted_absent_from_export: `True`
- exporter_candidate_append_absent: `True`
