# Frontend Map Pipeline Trace

- Generated: `2026-07-05T07:40:48+00:00`
- Frontend map file: `public/data/frontend-data.json`
- Frontend map rows: `1593`
- Join key strategy: `record_id+coordinate_pair`
- Confidence: `high`

## Pipeline

- The public frontend map is generated into `public/data/frontend-data.json`.
- `scripts/export_frontend_json.py` writes the `map_points` and `map_flags` arrays.
- `map_points` are selected from `record_locations` joined to `locations` and `records` by `is_public_map_location`, with one representative public map point per record.
- Internal V2 `narrative_locations` rows are audit/review rows and are not automatically public map flags.

## Manifest
- ID fields present: `record_id`
- Distinct record IDs: `1593`
- Distinct coordinate pairs: `871`
- Duplicate coordinate rows: `722`
- Rows with display/suppression fields: `0`

## Export Script Candidates
- `scripts/audit_1926_2011_gap.py`
- `scripts/audit_frontend_records.py`
- `scripts/audit_population_coverage.py`
- `scripts/build_experimental_gap_overlay.py`
- `scripts/build_gap_public_web_overlay.py`
- `scripts/build_live_gap_candidate_overlay.py`
- `scripts/check_vercel_release.py`
- `scripts/crawl_gap_abc_public_search.py`
- `scripts/crawl_gap_public_metadata.py`
- `scripts/export_frontend_json.py`
- `scripts/generate_release_reports.py`
- `scripts/import_gap_reviewed_candidates.py`
- `scripts/pre_frontend_freeze_audit.py`
- `scripts/reconcile_canonical_counts.py`
- `scripts/run_collection_sprint.py`
- `scripts/trace_frontend_map_pipeline.py`
- `scripts/update_current_collection_baseline.py`
- `scripts/validate_release.py`

## DB Table Candidates
- `records`
- `record_locations`
- `locations`
- `narrative_locations`
- `geocode_review_queue`
- `collection_candidates`

## Unresolved Questions
- None

## Source Search Hits
- `public/data/frontend-data.json` terms=density,figures,frontend,lat,latitude,lng,locations,longitude,map,mapped,public,records
- `public/data/frontend-data/v2.json` terms=density,figures,frontend,lat,latitude,lng,locations,longitude,map,public,records
- `scripts/export_dataset.py` terms=figures,lat,latitude,locations,longitude,public,records
- `scripts/healthify_location_hints.py` terms=lat,latitude,locations,longitude,map,public,records
- `scripts/build_gap_public_web_overlay.py` terms=frontend,lat,latitude,longitude,map,mapped,public,records
- `scripts/crawl_wikidata_gap_entities.py` terms=figures,frontend,lat,latitude,longitude,map,mapped,public,records
- `scripts/enrich_selected_existing_map_locations.py` terms=lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/audit_1926_2011_gap.py` terms=figures,frontend,lat,map,mapped,public,records
- `scripts/score_map_evidence.py` terms=frontend,lat,lng,map,mapped,public
- `scripts/reconcile_canonical_counts.py` terms=frontend,lat,latitude,lng,locations,longitude,map,mapped,public,records
- `scripts/pre_frontend_freeze_audit.py` terms=figures,frontend,lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/run_collection_sprint.py` terms=figures,frontend,lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/crawl_gap_public_metadata.py` terms=figures,frontend,lat,map,public,records
- `scripts/crawl_gap_abc_public_search.py` terms=figures,frontend,lat,latitude,longitude,map,mapped,public,records
- `scripts/promote_public_web_leads.py` terms=lat,latitude,longitude,map,mapped,public,records
- `scripts/collect_v2_batch.py` terms=density,lat,latitude,longitude,map,public,records
- `scripts/crawl_ayr_state_indexes.py` terms=figures,lat,latitude,longitude,map,mapped,public
- `scripts/geocode_location_queue.py` terms=lat,latitude,locations,longitude,map,public,records
- `scripts/audit_frontend_records.py` terms=frontend,map,mapped,public,records
- `scripts/import_gap_reviewed_candidates.py` terms=frontend,lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/validate_release.py` terms=frontend,map,mapped,public,records
- `scripts/crawl_public_books_metadata.py` terms=figures,frontend,lat,latitude,longitude,map,mapped,public,records
- `scripts/triage_existing_map_flags.py` terms=lat,latitude,lng,locations,longitude,map,mapped,public,records
- `scripts/export_v2.py` terms=frontend,lat,latitude,locations,longitude,map,public
- `scripts/build_live_gap_candidate_overlay.py` terms=figures,frontend,lat,latitude,longitude,map,mapped,public,records
- `scripts/trace_frontend_map_pipeline.py` terms=density,figures,frontend,lat,latitude,lng,locations,longitude,map,mapped,public,records
- `scripts/export_frontend_json.py` terms=figures,frontend,lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/build_experimental_gap_overlay.py` terms=figures,frontend,lat,latitude,longitude,map,mapped,public,records
- `scripts/crawl_wikipedia_haunted_locations.py` terms=figures,frontend,lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/update_current_collection_baseline.py` terms=frontend,lat,map,mapped,public,records
- `scripts/generate_release_reports.py` terms=figures,frontend,lat,map,mapped,public,records
- `scripts/crawl_hauntedplaces_australia.py` terms=lat,latitude,longitude,map,mapped,public
- `scripts/migrate_collection_expansion_v2.py` terms=lat,lng,map,public
- `scripts/healthcheck_ayr_location_hints.py` terms=lat,latitude,locations,longitude,public,records
- `scripts/repair_abc_known_site_locations.py` terms=lat,latitude,locations,longitude,map,records
- `scripts/audit_collection_balance.py` terms=lat,latitude,lng,locations,longitude,map,mapped,public,records
- `scripts/collect_ayr_records.py` terms=density,figures,frontend,lat,latitude,locations,longitude,map,public,records
- `scripts/convert_public_web_leads_to_gap_candidates.py` terms=frontend,lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/enrich_map_locations_from_public_records.py` terms=lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/check_vercel_release.py` terms=figures,frontend,lat,map,mapped,public,records
- `scripts/filter_gap_public_web_candidates.py` terms=lat,latitude,longitude,map,mapped,public
- `scripts/crawl_ayr_public_site_from_commoncrawl.py` terms=figures,frontend,lat,latitude,longitude,map,mapped,public,records
- `scripts/crawl_ayr_yowie_map.py` terms=lat,latitude,longitude,map,public
- `scripts/apply_legacy_map_triage.py` terms=lat,latitude,lng,locations,longitude,map,mapped,public
- `scripts/promote_accepted_candidates.py` terms=lat,latitude,locations,longitude,map,mapped,public,records
- `scripts/audit_population_coverage.py` terms=density,frontend,lat,map,mapped,public,records
- `src/aus_humanoid/geo.py` terms=lat,latitude,locations,longitude
- `src/aus_humanoid/models.py` terms=figures,lat,latitude,locations,longitude,public,records
