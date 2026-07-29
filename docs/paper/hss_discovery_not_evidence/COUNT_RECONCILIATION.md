# Paper Count Reconciliation

- Generated: `2026-07-06T15:34:31+00:00`
- Source stats JSON: `data/releases/paper_hss_discovery_not_evidence_20260706/paper_stats.json`

## Count Family Definitions

- `live_public_website_display_counts`: counts read from the deployed public website/runtime. These are not inferred from local files.
- `local_frontend_export_display_counts`: counts read from the local static frontend export.
- `legacy_flat_record_corpus_counts`: counts from the legacy `records` table.
- `v2_normalized_public_corpus_counts`: counts from normalized V2 tables and exports.
- `strict_no_credential_record_gate_experiment_counts`: counts from strict no-login/no-credential experiment tables and closeout configuration.
- `lead_mode_conversion_counts`: lead rows retained after strict record gates failed or were unsuitable.
- `priority_lead_counts`: lead rows with priority buckets or scores; these are not public records.
- `mapped_public_record_counts`: public-map and map-eligibility populations. Frontend map rows are not interchangeable with internal location rows.
- `source_organisation_source_type_counts`: source organisation and source type distributions.
- `source_family_concentration_counts`: source-family concentration for map rows and leads where fields exist.
- `blocker_counts`: blocker and evidence-gap counts for leads.
- `missingness_counts`: missing-field diagnostics for leads, narratives, and source items.

## Current Local Counts

| count_family | metric | value | unit | source | status | notes |
| --- | --- | ---: | --- | --- | --- | --- |
| live_public_website_display_counts | live_public_records |  | records | not available in current local data | not_available | Requires explicit capture from deployed website/runtime; local frontend exports are reported separately. |
| live_public_website_display_counts | live_public_mapped_records |  | records | not available in current local data | not_available | Requires explicit capture from deployed website/runtime; local frontend exports are reported separately. |
| local_frontend_export_display_counts | frontend_records | 4265 | records | public/data/frontend-data.json | ok |  |
| local_frontend_export_display_counts | frontend_map_points | 1593 | rows | public/data/frontend-data.json | ok |  |
| local_frontend_export_display_counts | frontend_map_flags | 1593 | rows | public/data/frontend-data.json | ok |  |
| local_frontend_export_display_counts | map_points_equal_map_flags | 1 | boolean_as_int | public/data/frontend-data.json | ok | 1 means local export satisfies map_points.length == map_flags.length. |
| frontend_release_package_counts | accepted_public_records | 4265 | rows | public/data/release-counts.json | ok |  |
| frontend_release_package_counts | accepted_public_map | 1593 | rows | public/data/release-counts.json | ok |  |
| frontend_release_package_counts | metadata_overlay | 1552 | rows | public/data/release-counts.json | ok |  |
| frontend_release_package_counts | lead_overlay | 1448 | rows | public/data/release-counts.json | ok |  |
| legacy_flat_record_corpus_counts | records_total | 4638 | records | records | ok |  |
| legacy_flat_record_corpus_counts | records_with_full_text_path | 1097 | records | records | ok |  |
| v2_normalized_public_corpus_counts | source_items_total | 4526 | source_items | source_items | ok |  |
| v2_normalized_public_corpus_counts | narrative_units_total | 4457 | narrative_units | narrative_units | ok |  |
| v2_normalized_public_corpus_counts | public_display_eligible_narrative_units | 4444 | narrative_units | narrative_units | ok | display_mode in full/summary_only/metadata_only and analysis_status not excluded. |
| source_chain_model_counts | narrative_source_links_total | 4457 | links | narrative_source_links | ok | Normalized link table count; not a proof-strength count. |
| source_chain_model_counts | source_chains_table_rows | 0 | rows | source_chains | ok | The local source_chains table may be empty even when source-chain audit files exist. |
| source_chain_model_counts | audit_source_chain_rows | 4526 | rows | data/processed/v2/source_chain_audit.csv | ok |  |
| source_chain_model_counts | audit_missing_original_source_name | 0 | rows | data/processed/v2/source_chain_audit.csv | ok |  |
| source_chain_model_counts | audit_tier_e_or_discovery_like_rows | 898 | rows | data/processed/v2/source_chain_audit.csv | ok |  |
| v2_normalized_public_corpus_counts | collection_candidates_v2_total | 5852 | candidates | collection_candidates_v2 | ok |  |
| strict_no_credential_record_gate_experiment_counts | provisional_records_total | 2762 | rows | provisional_records | ok |  |
| strict_no_credential_record_gate_experiment_counts | strict_target_gap_records | 0 | records | provisional_records | ok | Strict no-credential structured target-gap gate. |
| strict_no_credential_record_gate_experiment_counts | harvest_pages_seen | 94 | rows | harvest_pages | ok |  |
| strict_no_credential_record_gate_experiment_counts | harvest_candidates_seen | 7200 | rows | harvest_candidates | ok |  |
| strict_no_credential_record_gate_experiment_counts | structured_endpoints_seen | 22 | rows | noauth_endpoint_inventory | ok |  |
| strict_no_credential_record_gate_experiment_counts | structured_endpoint_records_seen | 120 | rows | noauth_endpoint_records | ok |  |
| strict_no_credential_record_gate_experiment_counts | structured_near_misses_materialized | 120 | rows | structured_endpoint_near_misses | ok |  |
| strict_no_credential_record_gate_experiment_counts | structured_enriched_records | 240 | rows | structured_endpoint_enriched_records | ok |  |
| strict_no_credential_record_gate_experiment_counts | strict_target_goal | 2000 | records | config/constraint_decision.yml | ok | Configuration target, not achieved count. |
| lead_mode_conversion_counts | target_gap_leads_total | 21343 | leads | target_gap_leads | ok |  |
| lead_mode_conversion_counts | lead_mode_enabled_config | 1 | boolean_as_int | config/constraint_decision.yml | ok |  |
| blocker_counts | top_constraint_blocker | 10320 | leads | target_gap_leads | ok | missing_date (48.35%). |
| blocker_counts | distinct_constraint_blockers | 6 | blockers | target_gap_leads | ok |  |
| source_family_concentration_counts | top_lead_source_family_count | 10950 | leads | target_gap_leads | ok | (missing) (51.3%). |
| source_family_concentration_counts | distinct_lead_source_families | 17 | families | target_gap_leads | ok |  |
| priority_lead_counts | lead_score_gte_80 | 10581 | leads | target_gap_leads | ok |  |
| mapped_public_record_counts | local_rule_map_eligible_narrative_locations | 1098 | rows | narrative_locations JOIN locations JOIN narrative_units | ok | Local rule denominator=4393; do not substitute for frontend map count. |
| mapped_public_record_counts | local_rule_map_eligibility_share_pct | 24.99 | percent | narrative_locations JOIN locations JOIN narrative_units | ok |  |
| source_organisation_source_type_counts | distinct_source_organisations | 315 | organisations | source_items | ok |  |
| source_organisation_source_type_counts | top_source_organisation_count | 898 | source_items | source_items | ok | Australian Yowie Research (19.84%). |
| source_organisation_source_type_counts | distinct_source_types | 26 | source_types | source_items | ok |  |
| source_organisation_source_type_counts | top_source_type_count | 1552 | source_items | source_items | ok | repository_full_text (34.29%). |
| missingness_counts | target_gap_leads_missing_temporal_signal | 10769 | leads | target_gap_leads | ok | 50.46% missing. |
| missingness_counts | target_gap_leads_missing_term_signal | 14361 | leads | target_gap_leads | ok | 67.29% missing. |
| missingness_counts | target_gap_leads_missing_place_signal | 11092 | leads | target_gap_leads | ok | 51.97% missing. |
| missingness_counts | target_gap_leads_missing_source_family | 10950 | leads | target_gap_leads | ok | 51.3% missing. |
| mapped_public_record_counts | canonical_frontend_public_records | 4265 | records | data/processed/v2/canonical_count_reconciliation.csv | ok |  |
| mapped_public_record_counts | canonical_frontend_public_map_rows | 1593 | rows | data/processed/v2/canonical_count_reconciliation.csv | ok |  |
| source_family_concentration_counts | top_frontend_map_source_family_count | 1272 | map_rows | data/processed/v2/frontend_source_concentration_audit.csv | ok | AYR_FAMILY (79.85%). |

## Not Available In Current Local Data

- `live_public_website_display_counts.live_public_records`: Requires explicit capture from deployed website/runtime; local frontend exports are reported separately.
- `live_public_website_display_counts.live_public_mapped_records`: Requires explicit capture from deployed website/runtime; local frontend exports are reported separately.

## Non-Mixing Rule

Do not combine live site display counts, local frontend export counts, legacy records, V2 normalized rows, strict-record experiment rows, lead-mode rows, or mapped rows unless a generated provenance table explicitly links the units.
