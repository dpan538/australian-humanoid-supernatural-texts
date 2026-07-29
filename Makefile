PYTHON ?= python3
PYTHON_ENV ?= PYTHONDONTWRITEBYTECODE=1
DB ?= data/processed/australian_humanoid_figures.sqlite

.PHONY: init seed queries trove-template trends-template pageviews-template collect-public-round collect-ayr-records plan-public-round-002 audit-round-002 locations validate export export-frontend frontend-audit dedupe test frontend-build snapshot-legacy migrate-v2 promote-accepted-candidates classify-legacy clean-v2 dedupe-v2 audit-v2 collection-baseline route-registry collect-v2-dry-run collect-v2-batch collect-v2-500 collect-v2-3000 export-v2 validate-v2 collection-expansion-migrate source-registry-sync plan-gap-queries probe-sources-dry-run audit-collection-balance audit-unmapped-place-hints release-gate-v2 triage-legacy-map-flags backfill-source-chains-dry-run sample-gap-probe-batch probe-gap-batch-dry-run make-review-packet trace-frontend-map reconcile-canonical-counts score-map-evidence score-source-chains score-probe-candidates evaluate-route-yield plan-source-chain-remediation plan-first-real-probe summarize-actionable-rows nonexpert-dashboard machine-evaluate-all machine-map-cleanup-dry-run audit-frontend-source-concentration plan-late-gap-institutional-probe plan-source-chain-replacement-searches score-source-chain-remediation-impact phase5-plan run-first-real-trove-probe noauth-plan-open-probe noauth-sitemap-dry-run noauth-probe-dry-run noauth-probe-execute noauth-pdf-metadata-dry-run noauth-score-candidates noauth-evaluate-yield noauth-discover-missing-routes-dry-run noauth-open-sprint-dry-run noauth-open-sprint-evaluate autoharvest-migrate autoharvest-dry-run autoharvest-start autoharvest-checkpoint autoharvest-watchdog autoharvest-rebalance autoharvest-milestone-audit autoharvest-operator-summary autoharvest-gap-migrate autoharvest-gap-discover-search-forms autoharvest-gap-reclassify-previous autoharvest-gap-build-frontier autoharvest-gap-start autoharvest-gap-checkpoint autoharvest-gap-rebalance autoharvest-gap-pdf-snippets autoharvest-gap-milestone-audit autoharvest-gap-preflight gap-zero-yield-postmortem gap-discover-search-forms gap-build-target-acquisition-plan gap-viability-test gap-target-acquisition-operator gap-target-acquisition-preflight gap-recover-near-misses gap-deepen-pdf-newsletters gap-repair-search-forms gap-public-index-discovery gap-access-platform-mining gap-expand-source-atlas gap-recovery-operator gap-recovery-preflight structured-endpoint-migrate structured-endpoint-discover structured-endpoint-build-queries structured-endpoint-start structured-endpoint-checkpoint structured-endpoint-access-platforms structured-endpoint-milestone-audit no-credential-infeasibility-report structured-endpoint-preflight structured-metrics-audit structured-near-miss-migrate structured-materialize-near-misses structured-debug-adapters structured-enrich-near-misses structured-rebuild-enriched-queries structured-enrichment-operator structured-enrichment-preflight structured-robots-block-audit structured-enrich-existing-metadata structured-repair-atom-atomm structured-enrich-rss-inline structured-discover-detail-alternatives structured-enrich-detail-alternatives structured-robots-aware-rescue public-artifact-baseline public-artifact-check structured-robots-aware-preflight

init:
	$(PYTHON_ENV) $(PYTHON) scripts/init_db.py --db $(DB)

seed:
	$(PYTHON_ENV) $(PYTHON) scripts/seed_lexicon.py --db $(DB)

queries:
	$(PYTHON_ENV) $(PYTHON) scripts/build_queries.py --db $(DB)

trove-template:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_trove_stub.py --db $(DB)

trends-template:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_google_trends_stub.py

pageviews-template:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_wikimedia_pageviews_stub.py

collect-public-round:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_public_round.py --db $(DB)

collect-ayr-records:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_ayr_records.py --db $(DB) --target 200

plan-public-round-002:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_public_round_002.py --db $(DB)

audit-round-002:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_round_coverage.py --db $(DB) --round-prefix public_round_002

locations:
	$(PYTHON_ENV) $(PYTHON) scripts/enrich_locations.py --db $(DB)

validate:
	$(PYTHON_ENV) $(PYTHON) scripts/validate_records.py --db $(DB)

export:
	$(PYTHON_ENV) $(PYTHON) scripts/export_dataset.py --db $(DB)

export-frontend:
	$(PYTHON_ENV) $(PYTHON) scripts/export_frontend_json.py --db $(DB)
	$(PYTHON_ENV) $(PYTHON) scripts/export_v2.py --db $(DB)
	$(PYTHON_ENV) $(PYTHON) scripts/audit_frontend_records.py --sample-size 50

frontend-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_frontend_records.py --sample-size 50

dedupe:
	$(PYTHON_ENV) $(PYTHON) scripts/run_dedupe.py --db $(DB)

test:
	$(PYTHON_ENV) $(PYTHON) scripts/run_tests.py

frontend-build:
	npm run build

snapshot-legacy:
	$(PYTHON_ENV) $(PYTHON) scripts/snapshot_legacy.py --db $(DB)

migrate-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_legacy_records_v2.py --db $(DB)

promote-accepted-candidates:
	$(PYTHON_ENV) $(PYTHON) scripts/promote_accepted_candidates.py --db $(DB)

classify-legacy: migrate-v2

clean-v2: migrate-v2

dedupe-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/run_dedupe.py --db $(DB)

audit-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_v2.py --db $(DB)

collection-baseline:
	$(PYTHON_ENV) $(PYTHON) scripts/update_current_collection_baseline.py --db $(DB)

route-registry:
	$(PYTHON_ENV) $(PYTHON) scripts/update_collection_route_registry.py

collect-v2-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_v2_batch.py --db $(DB) --run-id v2_collection_batch_001 --trove-leads --limit 50 --route-id trove_api_without_key

collect-v2-batch:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_v2_batch.py --db $(DB) --run-id v2_collection_batch_001 --trove-leads --limit 50 --route-id trove_api_without_key

collect-v2-500:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_v2_batch.py --db $(DB) --run-id v2_collection_batch_001 --trove-leads --limit 50 --route-id trove_api_without_key

collect-v2-3000:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_v2_batch.py --db $(DB) --run-id strict_geo_collection_3000_batch_001 --trove-leads --limit 50 --strict-geo-only --target 3000 --report data/processed/v2/collection_3000_strict_geo_progress.md --route-id trove_api_without_key

export-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/export_v2.py --db $(DB)

validate-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/validate_v2.py --db $(DB)

collection-expansion-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_collection_expansion_v2.py --db $(DB)

source-registry-sync: collection-expansion-migrate
	$(PYTHON_ENV) $(PYTHON) scripts/sync_source_registry.py --db $(DB) --config config/source_registry.yml

plan-gap-queries:
	$(PYTHON_ENV) $(PYTHON) scripts/build_gap_query_matrix.py --matrix config/query_matrix_1926_1976.yml --registry config/source_registry.yml --targets config/collection_targets.yml --out data/interim/collection_plans/query_matrix_1926_1976.csv

probe-sources-dry-run: collection-expansion-migrate source-registry-sync plan-gap-queries
	$(PYTHON_ENV) $(PYTHON) scripts/probe_public_sources.py --db $(DB) --registry config/source_registry.yml --query-plan data/interim/collection_plans/query_matrix_1926_1976.csv --run-id gap_probe_dry_run --limit 50 --dry-run

audit-collection-balance:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_collection_balance.py --db $(DB) --targets config/collection_targets.yml --out-dir data/processed/v2

audit-unmapped-place-hints:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_unmapped_place_hints.py --db $(DB) --out data/review/v2/unmapped_place_hint_review.csv

release-gate-v2: audit-v2 audit-collection-balance validate-v2
	$(PYTHON_ENV) $(PYTHON) scripts/check_collection_release_gates.py --db $(DB) --targets config/collection_targets.yml

triage-legacy-map-flags:
	$(PYTHON_ENV) $(PYTHON) scripts/triage_existing_map_flags.py --db $(DB) --out data/review/v2/legacy_map_flag_triage.csv --report data/processed/v2/legacy_map_flag_triage_report.md

backfill-source-chains-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/backfill_source_chains_existing.py --db $(DB) --registry config/source_registry.yml --out data/review/v2/source_chain_backfill_review.csv --report data/processed/v2/source_chain_backfill_report.md --dry-run

sample-gap-probe-batch:
	$(PYTHON_ENV) $(PYTHON) scripts/sample_gap_probe_jobs.py --query-plan data/interim/collection_plans/query_matrix_1926_1976.csv --registry config/source_registry.yml --targets config/collection_targets.yml --out data/interim/collection_plans/gap_probe_batch_001.csv --batch-size 300 --seed 42

probe-gap-batch-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/probe_public_sources.py --db $(DB) --registry config/source_registry.yml --query-plan data/interim/collection_plans/gap_probe_batch_001.csv --run-id gap_probe_batch_001 --limit 300 --dry-run

make-review-packet:
	$(PYTHON_ENV) $(PYTHON) scripts/make_review_packet.py --db $(DB) --run-id gap_probe_batch_001 --out-dir data/review/v2/packets/gap_probe_batch_001 --max-items 300

trace-frontend-map:
	$(PYTHON_ENV) $(PYTHON) scripts/trace_frontend_map_pipeline.py --repo-root . --db $(DB) --frontend-dir frontend --exports-dir data/exports/v2 --out-dir data/processed/v2

reconcile-canonical-counts: trace-frontend-map
	$(PYTHON_ENV) $(PYTHON) scripts/reconcile_canonical_counts.py --db $(DB) --frontend-dir frontend/src/data --exports-dir data/exports/v2 --out-dir data/processed/v2

score-map-evidence: reconcile-canonical-counts triage-legacy-map-flags
	$(PYTHON_ENV) $(PYTHON) scripts/score_map_evidence.py --db $(DB) --canonical-map data/processed/v2/canonical_public_map_population.csv --triage-csv data/review/v2/legacy_map_flag_triage.csv --out data/review/v2/map_evidence_machine_scores.csv --report data/processed/v2/map_evidence_machine_score_report.md

score-source-chains: backfill-source-chains-dry-run
	$(PYTHON_ENV) $(PYTHON) scripts/score_source_chains.py --db $(DB) --backfill-review data/review/v2/source_chain_backfill_review.csv --registry config/source_registry.yml --out data/review/v2/source_chain_machine_scores.csv --report data/processed/v2/source_chain_score_report.md

score-probe-candidates:
	$(PYTHON_ENV) $(PYTHON) scripts/score_probe_candidates.py --db $(DB) --run-id gap_probe_batch_001 --out data/processed/v2/probe_candidate_scores.csv --report data/processed/v2/probe_candidate_score_report.md --limit 1000

evaluate-route-yield: score-source-chains score-probe-candidates
	$(PYTHON_ENV) $(PYTHON) scripts/evaluate_route_yield.py --candidate-scores data/processed/v2/probe_candidate_scores.csv --source-chain-scores data/review/v2/source_chain_machine_scores.csv --out data/processed/v2/route_yield_evaluation.csv --report data/processed/v2/route_yield_evaluation_report.md

plan-source-chain-remediation: score-source-chains
	$(PYTHON_ENV) $(PYTHON) scripts/plan_source_chain_remediation.py --source-chain-scores data/review/v2/source_chain_machine_scores.csv --out-dir data/review/v2/source_chain_remediation

plan-first-real-probe:
	$(PYTHON_ENV) $(PYTHON) scripts/plan_first_real_probe.py --query-plan data/interim/collection_plans/gap_probe_batch_001.csv --registry config/source_registry.yml --out data/interim/collection_plans/first_real_trove_probe_plan.csv --report data/processed/v2/first_real_trove_probe_plan.md --max-queries 50

summarize-actionable-rows:
	$(PYTHON_ENV) $(PYTHON) scripts/summarize_actionable_rows.py --map-scores data/review/v2/map_evidence_machine_scores.csv --source-chain-scores data/review/v2/source_chain_machine_scores.csv --route-yield data/processed/v2/route_yield_evaluation.csv --out data/processed/v2/actionable_rows_summary.md

nonexpert-dashboard:
	$(PYTHON_ENV) $(PYTHON) scripts/make_nonexpert_dashboard.py --out data/processed/v2/nonexpert_machine_evaluation_dashboard.md

machine-evaluate-all: trace-frontend-map reconcile-canonical-counts score-map-evidence score-source-chains score-probe-candidates evaluate-route-yield plan-source-chain-remediation plan-first-real-probe summarize-actionable-rows nonexpert-dashboard

machine-map-cleanup-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/apply_machine_map_cleanup.py --db $(DB) --scores data/review/v2/map_evidence_machine_scores.csv --reconciliation data/processed/v2/canonical_count_reconciliation.md --run-id machine_map_cleanup_001 --out data/processed/v2/machine_map_cleanup_dry_run.csv --report data/processed/v2/machine_map_cleanup_dry_run_report.md --dry-run --min-confidence 0.95

audit-frontend-source-concentration:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_frontend_source_concentration.py --frontend-map data/processed/v2/frontend_map_manifest.csv --canonical-map data/processed/v2/canonical_public_map_population.csv --out data/processed/v2/frontend_source_concentration_audit.csv --report data/processed/v2/frontend_source_concentration_audit.md

plan-late-gap-institutional-probe:
	$(PYTHON_ENV) $(PYTHON) scripts/plan_late_gap_institutional_probe.py --registry config/source_registry.yml --matrix config/query_matrix_1926_1976.yml --targets config/collection_targets.yml --out data/interim/collection_plans/late_gap_1955_1976_institutional_probe_plan.csv --manual-out data/interim/collection_plans/late_gap_1955_1976_manual_review_plan.csv --report data/processed/v2/late_gap_1955_1976_institutional_probe_plan.md --max-automated 150 --max-manual 300

plan-source-chain-replacement-searches:
	$(PYTHON_ENV) $(PYTHON) scripts/plan_source_chain_replacement_searches.py --source-chain-scores data/review/v2/source_chain_machine_scores.csv --registry config/source_registry.yml --canonical-map data/processed/v2/canonical_public_map_population.csv --out data/review/v2/source_chain_remediation/replacement_search_tasks.csv --report data/review/v2/source_chain_remediation/replacement_search_tasks.md --max-tasks 500

score-source-chain-remediation-impact:
	$(PYTHON_ENV) $(PYTHON) scripts/score_source_chain_remediation_impact.py --frontend-source-audit data/processed/v2/frontend_source_concentration_audit.csv --replacement-tasks data/review/v2/source_chain_remediation/replacement_search_tasks.csv --out data/processed/v2/source_chain_remediation_impact.csv --report data/processed/v2/source_chain_remediation_impact.md

phase5-plan:
	$(MAKE) audit-frontend-source-concentration
	$(MAKE) plan-source-chain-replacement-searches
	$(MAKE) score-source-chain-remediation-impact
	$(MAKE) plan-late-gap-institutional-probe
	$(MAKE) nonexpert-dashboard

run-first-real-trove-probe:
	$(PYTHON_ENV) $(PYTHON) scripts/run_first_real_probe_workflow.py --db $(DB) --query-plan data/interim/collection_plans/first_real_trove_probe_plan.csv --run-id trove_first_real_probe_001 --limit 50 --max-results-per-query 5 --execute

noauth-plan-open-probe:
	$(PYTHON_ENV) $(PYTHON) scripts/build_noauth_open_probe_plan.py --seeds config/noauth_open_source_seeds.yml --matrix config/query_matrix_1926_1976.yml --targets config/collection_targets.yml --out data/interim/collection_plans/noauth_open_probe_plan.csv --manual-out data/interim/collection_plans/noauth_manual_review_tasks.csv --report data/processed/v2/noauth_open_probe_plan.md --max-automated 500 --max-manual 500

noauth-sitemap-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/noauth_discover_sitemaps.py --seeds config/noauth_open_source_seeds.yml --out data/interim/source_discovery/noauth_sitemap_inventory.csv --report data/processed/v2/noauth_sitemap_inventory.md --limit-routes 100 --dry-run

noauth-probe-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/noauth_probe_open_routes.py --db $(DB) --plan data/interim/collection_plans/noauth_open_probe_plan.csv --run-id noauth_open_probe_001 --limit 200 --dry-run

noauth-probe-execute:
	$(PYTHON_ENV) $(PYTHON) scripts/noauth_probe_open_routes.py --db $(DB) --plan data/interim/collection_plans/noauth_open_probe_plan.csv --run-id noauth_open_probe_001 --limit 200 --execute

noauth-pdf-metadata-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/noauth_probe_pdf_metadata.py --plan data/interim/collection_plans/noauth_open_probe_plan.csv --out data/interim/source_discovery/noauth_pdf_metadata.csv --report data/processed/v2/noauth_pdf_metadata_report.md --limit 300 --dry-run

noauth-score-candidates:
	$(PYTHON_ENV) $(PYTHON) scripts/noauth_score_open_candidates.py --db $(DB) --run-id noauth_open_probe_001 --candidate-csv data/review/v2/noauth_open_probe_001_candidate_review.csv --out data/review/v2/noauth_open_probe_001_candidate_scores.csv --report data/processed/v2/noauth_open_probe_001_candidate_score_report.md

noauth-evaluate-yield:
	$(PYTHON_ENV) $(PYTHON) scripts/noauth_evaluate_route_yield.py --scores data/review/v2/noauth_open_probe_001_candidate_scores.csv --out data/processed/v2/noauth_route_yield.csv --report data/processed/v2/noauth_route_yield.md

noauth-discover-missing-routes-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/noauth_discover_missing_routes.py --seeds config/noauth_open_source_seeds.yml --out data/interim/source_discovery/noauth_discovered_route_candidates.csv --report data/processed/v2/noauth_discovered_route_candidates.md --limit 500 --dry-run

noauth-open-sprint-dry-run: noauth-plan-open-probe noauth-sitemap-dry-run noauth-probe-dry-run noauth-pdf-metadata-dry-run noauth-discover-missing-routes-dry-run

noauth-open-sprint-evaluate: noauth-score-candidates noauth-evaluate-yield nonexpert-dashboard

autoharvest-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_autoharvest_v1.py --db $(DB)

autoharvest-dry-run: autoharvest-migrate
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_open_records.py --db $(DB) --config config/autoharvest.yml --seeds config/noauth_open_source_seeds.yml --run-id noauth_marathon_001 --target-effective-records 2000 --dry-run

autoharvest-start: autoharvest-migrate
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_supervisor.py --db $(DB) --config config/autoharvest.yml --seeds config/noauth_open_source_seeds.yml --run-id noauth_marathon_001 --target-effective-records 2000 --execute

autoharvest-checkpoint:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_checkpoint_report.py --db $(DB) --run-id noauth_marathon_001 --out data/processed/v2/autoharvest/noauth_marathon_001_checkpoint.md

autoharvest-watchdog:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_watchdog.py --db $(DB) --run-id noauth_marathon_001 --out data/processed/v2/autoharvest/noauth_marathon_001_watchdog.md

autoharvest-rebalance:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_build_next_frontier.py --db $(DB) --run-id noauth_marathon_001 --config config/autoharvest.yml --out data/processed/v2/autoharvest/noauth_marathon_001_frontier_rebalance.md

autoharvest-milestone-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_milestone_audit.py --db $(DB) --run-id noauth_marathon_001 --target-effective-records 2000 --out-dir data/processed/v2/autoharvest/milestone_2000

autoharvest-operator-summary:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_operator_summary.py --db $(DB) --run-id noauth_marathon_001 --out data/processed/v2/autoharvest/noauth_marathon_001_operator_summary.md

autoharvest-gap-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_autoharvest_gap_v2.py --db $(DB)

autoharvest-gap-discover-search-forms:
	$(PYTHON_ENV) $(PYTHON) scripts/discover_noauth_search_forms.py --seeds config/noauth_open_source_seeds.yml --out data/interim/source_discovery/noauth_search_forms.csv --report data/processed/v2/noauth_search_forms.md --execute

autoharvest-gap-reclassify-previous:
	$(PYTHON_ENV) $(PYTHON) scripts/rescore_autoharvest_temporal_targets.py --db $(DB) --config config/autoharvest_gap_rescue.yml --run-id noauth_marathon_001 --out data/processed/v2/autoharvest/noauth_marathon_001_temporal_reclassification.md --execute

autoharvest-gap-build-frontier:
	$(PYTHON_ENV) $(PYTHON) scripts/build_gap_targeted_noauth_frontier.py --db $(DB) --config config/autoharvest_gap_rescue.yml --seeds config/noauth_open_source_seeds.yml --search-forms data/interim/source_discovery/noauth_search_forms.csv --run-id noauth_gap_marathon_001 --out data/processed/v2/autoharvest/gap_targeted_frontier_plan.md --execute

autoharvest-gap-start:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_gap_supervisor.py --db $(DB) --config config/autoharvest_gap_rescue.yml --seeds config/noauth_open_source_seeds.yml --run-id noauth_gap_marathon_001 --target-gap-effective-records 2000 --execute

autoharvest-gap-checkpoint:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_gap_checkpoint_report.py --db $(DB) --run-id noauth_gap_marathon_001 --out data/processed/v2/autoharvest/noauth_gap_marathon_001_checkpoint.md

autoharvest-gap-rebalance:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_gap_rebalance.py --db $(DB) --config config/autoharvest_gap_rescue.yml --run-id noauth_gap_marathon_001 --out data/processed/v2/autoharvest/noauth_gap_marathon_001_rebalance.md

autoharvest-gap-pdf-snippets:
	$(PYTHON_ENV) $(PYTHON) scripts/probe_public_pdf_snippets_gap.py --db $(DB) --config config/autoharvest_gap_rescue.yml --run-id noauth_gap_marathon_001 --limit 100 --execute

autoharvest-gap-milestone-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/autoharvest_gap_milestone_audit.py --db $(DB) --run-id noauth_gap_marathon_001 --target-gap-effective-records 2000 --out-dir data/processed/v2/autoharvest/gap_milestone_2000

autoharvest-gap-preflight:
	$(MAKE) autoharvest-gap-migrate
	$(MAKE) autoharvest-gap-discover-search-forms
	$(MAKE) autoharvest-gap-reclassify-previous
	$(MAKE) autoharvest-gap-build-frontier
	$(MAKE) test
	$(MAKE) export-v2
	$(MAKE) validate-v2
	$(MAKE) export-frontend
	$(MAKE) autoharvest-watchdog

gap-zero-yield-postmortem:
	$(PYTHON_ENV) $(PYTHON) scripts/analyze_gap_zero_yield.py --db $(DB) --run-id noauth_gap_marathon_001 --out-dir data/processed/v2/autoharvest/zero_yield_postmortem

gap-discover-search-forms:
	$(PYTHON_ENV) $(PYTHON) scripts/discover_noauth_search_forms.py --seeds config/noauth_open_source_seeds.yml --out data/interim/source_discovery/noauth_search_forms.csv --report data/processed/v2/noauth_search_forms.md --execute

gap-build-target-acquisition-plan:
	$(PYTHON_ENV) $(PYTHON) scripts/build_target_acquisition_plan.py --db $(DB) --postmortem-dir data/processed/v2/autoharvest/zero_yield_postmortem --seeds config/noauth_open_source_seeds.yml --registry config/source_registry.yml --matrix config/query_matrix_1926_1976.yml --out data/interim/collection_plans/target_acquisition_plan.csv --report data/processed/v2/autoharvest/target_acquisition_plan.md --max-actions 1000

gap-viability-test:
	$(PYTHON_ENV) $(PYTHON) scripts/run_target_acquisition_viability_test.py --db $(DB) --plan data/interim/collection_plans/target_acquisition_plan.csv --run-id noauth_gap_viability_001 --max-actions 500 --execute

gap-target-acquisition-operator:
	$(PYTHON_ENV) $(PYTHON) scripts/target_acquisition_operator.py --db $(DB) --config config/autoharvest_gap_rescue.yml --run-id noauth_gap_marathon_001 --target-gap-effective-records 2000 --execute

gap-target-acquisition-preflight:
	$(MAKE) gap-zero-yield-postmortem
	$(MAKE) gap-discover-search-forms
	$(MAKE) gap-build-target-acquisition-plan
	$(MAKE) test
	$(MAKE) export-v2
	$(MAKE) validate-v2
	$(MAKE) export-frontend
	$(MAKE) autoharvest-watchdog

gap-recover-near-misses:
	$(PYTHON_ENV) $(PYTHON) scripts/recover_gap_near_misses.py --db $(DB) --run-id noauth_gap_viability_001 --out-dir data/processed/v2/autoharvest/recovery_near_misses --execute

gap-deepen-pdf-newsletters:
	$(PYTHON_ENV) $(PYTHON) scripts/deepen_viable_pdf_newsletter_routes.py --db $(DB) --viability-dir data/processed/v2/autoharvest/target_acquisition_viability --run-id noauth_gap_pdf_deepening_001 --limit-routes 20 --limit-pdfs-per-route 100 --execute

gap-repair-search-forms:
	$(PYTHON_ENV) $(PYTHON) scripts/cluster_and_repair_search_forms.py --search-forms data/interim/source_discovery/noauth_search_forms.csv --viability-dir data/processed/v2/autoharvest/target_acquisition_viability --out-dir data/processed/v2/autoharvest/search_form_repair --execute

gap-public-index-discovery:
	$(PYTHON_ENV) $(PYTHON) scripts/discover_targets_via_public_url_indexes.py --db $(DB) --seeds config/noauth_open_source_seeds.yml --registry config/source_registry.yml --run-id noauth_gap_index_discovery_001 --out-dir data/processed/v2/autoharvest/public_index_discovery --limit-domains 200 --limit-url-hits-per-domain 200 --execute

gap-access-platform-mining:
	$(PYTHON_ENV) $(PYTHON) scripts/mine_noauth_access_platforms_for_gap.py --db $(DB) --registry config/source_registry.yml --run-id noauth_gap_access_platform_001 --out-dir data/processed/v2/autoharvest/access_platform_gap_mining --execute

gap-expand-source-atlas:
	$(PYTHON_ENV) $(PYTHON) scripts/expand_routes_from_source_atlas.py --atlas docs/research/SOURCE_ROUTE_ATLAS_SEED.md --registry config/source_registry.yml --seeds config/noauth_open_source_seeds.yml --out config/noauth_open_source_seeds_expanded.yml --report data/processed/v2/autoharvest/source_atlas_expansion_report.md

gap-recovery-operator:
	$(PYTHON_ENV) $(PYTHON) scripts/noauth_gap_recovery_operator.py --db $(DB) --config config/autoharvest_gap_rescue.yml --run-id noauth_gap_recovery_001 --target-gap-effective-records 2000 --execute

gap-recovery-preflight:
	$(MAKE) gap-recover-near-misses
	$(MAKE) gap-deepen-pdf-newsletters
	$(MAKE) gap-repair-search-forms
	$(MAKE) gap-expand-source-atlas
	$(MAKE) test
	$(MAKE) export-v2
	$(MAKE) validate-v2
	$(MAKE) export-frontend
	$(MAKE) autoharvest-watchdog

structured-endpoint-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_structured_endpoint_harvest_v1.py --db $(DB)

structured-endpoint-discover: structured-endpoint-migrate
	$(PYTHON_ENV) $(PYTHON) scripts/discover_noauth_structured_endpoints.py --db $(DB) --config config/noauth_structured_endpoints.yml --seeds config/noauth_open_source_seeds.yml --registry config/source_registry.yml --expanded-seeds config/noauth_open_source_seeds_expanded.yml --out data/processed/v2/autoharvest/structured_endpoints/endpoint_discovery_report.md --execute

structured-endpoint-build-queries: structured-endpoint-migrate
	$(PYTHON_ENV) $(PYTHON) scripts/build_structured_endpoint_queries.py --db $(DB) --config config/noauth_structured_endpoints.yml --run-id noauth_structured_endpoint_001 --out data/processed/v2/autoharvest/structured_endpoints/structured_endpoint_query_plan.md --execute

structured-endpoint-start: structured-endpoint-migrate
	$(PYTHON_ENV) $(PYTHON) scripts/run_structured_endpoint_gap_operator.py --db $(DB) --config config/noauth_structured_endpoints.yml --run-id noauth_structured_endpoint_001 --target-gap-effective-records 2000 --execute

structured-endpoint-checkpoint:
	$(PYTHON_ENV) $(PYTHON) scripts/structured_endpoint_checkpoint_report.py --db $(DB) --run-id noauth_structured_endpoint_001 --out data/processed/v2/autoharvest/structured_endpoints/noauth_structured_endpoint_001_checkpoint.md

structured-endpoint-access-platforms:
	$(PYTHON_ENV) $(PYTHON) scripts/probe_noauth_access_platform_endpoints.py --db $(DB) --registry config/source_registry.yml --run-id noauth_structured_endpoint_access_001 --out-dir data/processed/v2/autoharvest/structured_endpoints/access_platforms --execute

structured-endpoint-milestone-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/structured_endpoint_milestone_audit.py --db $(DB) --run-id noauth_structured_endpoint_001 --target-effective-records 250 --out-dir data/processed/v2/autoharvest/structured_endpoints/milestone_250

structured-metrics-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_structured_endpoint_metrics.py --db $(DB) --run-id noauth_structured_endpoint_001 --out-dir data/processed/v2/autoharvest/structured_endpoints/metrics_audit

structured-near-miss-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_structured_near_miss_v1.py --db $(DB)

structured-materialize-near-misses:
	$(PYTHON_ENV) $(PYTHON) scripts/materialize_structured_near_misses.py --db $(DB) --run-id noauth_structured_endpoint_001 --out data/review/v2/autoharvest/structured_endpoints/noauth_structured_endpoint_001_near_misses_materialized.csv --report data/processed/v2/autoharvest/structured_endpoints/near_miss_materialization_report.md --execute

structured-debug-adapters:
	$(PYTHON_ENV) $(PYTHON) scripts/debug_structured_endpoint_adapters.py --db $(DB) --run-id noauth_structured_endpoint_001 --out-dir data/processed/v2/autoharvest/structured_endpoints/adapter_debug

structured-enrich-near-misses:
	$(PYTHON_ENV) $(PYTHON) scripts/enrich_structured_near_misses.py --db $(DB) --run-id noauth_structured_endpoint_001 --limit 200 --execute

structured-rebuild-enriched-queries:
	$(PYTHON_ENV) $(PYTHON) scripts/rebuild_structured_queries_from_materialized_near_misses.py --db $(DB) --run-id noauth_structured_endpoint_001 --new-run-id noauth_structured_endpoint_enriched_001 --out data/processed/v2/autoharvest/structured_endpoints/enriched_query_rebuild_report.md --execute

structured-enrichment-operator:
	$(PYTHON_ENV) $(PYTHON) scripts/run_structured_endpoint_enrichment_operator.py --db $(DB) --base-run-id noauth_structured_endpoint_001 --run-id noauth_structured_endpoint_enrichment_001 --target-gap-effective-records 2000 --execute

no-credential-infeasibility-report:
	$(PYTHON_ENV) $(PYTHON) scripts/no_credential_infeasibility_report.py --db $(DB) --structured-run-id noauth_structured_endpoint_001 --recovery-summary data/processed/v2/autoharvest/noauth_gap_recovery_operator_summary.md --structured-checkpoint data/processed/v2/autoharvest/structured_endpoints/noauth_structured_endpoint_001_checkpoint.md --out data/processed/v2/autoharvest/no_credential_infeasibility_report.md

structured-endpoint-preflight:
	$(MAKE) structured-endpoint-migrate
	$(MAKE) structured-endpoint-discover
	$(MAKE) structured-endpoint-build-queries
	$(MAKE) test
	$(MAKE) export-v2
	$(MAKE) validate-v2
	$(MAKE) export-frontend
	$(MAKE) autoharvest-watchdog

structured-enrichment-preflight:
	$(MAKE) structured-metrics-audit
	$(MAKE) structured-near-miss-migrate
	$(MAKE) structured-materialize-near-misses
	$(MAKE) structured-debug-adapters
	$(MAKE) test
	$(MAKE) export-v2
	$(MAKE) validate-v2
	$(MAKE) export-frontend
	$(MAKE) autoharvest-watchdog

structured-robots-block-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_near_miss_robots_block.py --db $(DB) --run-id noauth_structured_endpoint_001 --out-dir data/processed/v2/autoharvest/structured_endpoints/robots_block_audit

structured-enrich-existing-metadata:
	$(PYTHON_ENV) $(PYTHON) scripts/enrich_from_existing_endpoint_metadata.py --db $(DB) --run-id noauth_structured_endpoint_001 --out data/review/v2/autoharvest/structured_endpoints/existing_metadata_enrichment_candidates.csv --report data/processed/v2/autoharvest/structured_endpoints/existing_metadata_enrichment_report.md --execute

structured-repair-atom-atomm:
	$(PYTHON_ENV) $(PYTHON) scripts/repair_atom_atomm_adapter.py --db $(DB) --run-id noauth_structured_endpoint_001 --out-dir data/processed/v2/autoharvest/structured_endpoints/atom_atomm_repair --execute

structured-enrich-rss-inline:
	$(PYTHON_ENV) $(PYTHON) scripts/enrich_rss_items_inline.py --db $(DB) --run-id noauth_structured_endpoint_001 --out-dir data/processed/v2/autoharvest/structured_endpoints/rss_inline_enrichment --execute

structured-discover-detail-alternatives:
	$(PYTHON_ENV) $(PYTHON) scripts/discover_allowed_detail_alternatives.py --db $(DB) --run-id noauth_structured_endpoint_001 --out data/processed/v2/autoharvest/structured_endpoints/allowed_detail_alternatives.csv --report data/processed/v2/autoharvest/structured_endpoints/allowed_detail_alternatives_report.md --execute

structured-enrich-detail-alternatives:
	$(PYTHON_ENV) $(PYTHON) scripts/enrich_allowed_detail_alternatives.py --db $(DB) --alternatives data/processed/v2/autoharvest/structured_endpoints/allowed_detail_alternatives.csv --run-id noauth_structured_endpoint_001 --limit 200 --execute

structured-robots-aware-rescue:
	$(PYTHON_ENV) $(PYTHON) scripts/run_robots_aware_near_miss_rescue_operator.py --db $(DB) --run-id noauth_structured_endpoint_001 --target-gap-effective-records 2000 --execute

public-artifact-baseline:
	$(PYTHON_ENV) $(PYTHON) scripts/assert_no_public_artifact_diff.py --repo-root . --baseline-file data/processed/v2/autoharvest/public_artifact_baseline.json --create-baseline

public-artifact-check:
	$(PYTHON_ENV) $(PYTHON) scripts/assert_no_public_artifact_diff.py --repo-root . --baseline-file data/processed/v2/autoharvest/public_artifact_baseline.json --check

structured-robots-aware-preflight:
	$(MAKE) public-artifact-baseline
	$(MAKE) structured-robots-block-audit
	$(MAKE) test
	$(MAKE) validate-v2
	$(MAKE) public-artifact-check
	$(MAKE) autoharvest-watchdog

.PHONY: target-gap-leads-migrate strict-no-credential-closeout convert-failures-to-leads score-target-gap-leads cluster-target-gap-leads simulate-constraint-relaxation no-human-lead-dashboard tiny-review-packet lead-mode-start strict-closeout-and-lead-plan lead-population-audit lead-dedupe lead-date-salvage metadata-only-1955-1976-layer lead-blocker-analysis lead-observation-dashboard lead-mode-start-decision source-intelligence-brief lead-intelligence-all research-volume-migrate research-volume-scheduler research-volume-expand research-volume-dashboard research-volume-all release-freeze-inputs release-coverage-1926-2011 release-bounded-patch-plan release-layers-migrate release-apply-bounded-patch release-final-map-layers release-redirects-migrate release-build-redirects release-validate-redirects release-build-package release-final-audit release-dashboard release-sprint-all release-apply-package-dry-run release-apply-package

target-gap-leads-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_target_gap_leads_v1.py --db $(DB)

strict-no-credential-closeout:
	$(PYTHON_ENV) $(PYTHON) scripts/finalize_strict_no_credential_closeout.py --db $(DB) --config config/constraint_decision.yml --out-dir data/processed/v2/autoharvest/strict_closeout

convert-failures-to-leads:
	$(PYTHON_ENV) $(PYTHON) scripts/convert_failures_to_target_gap_leads.py --db $(DB) --config config/constraint_decision.yml --out data/processed/v2/autoharvest/target_gap_leads/target_gap_leads_created.md --execute

score-target-gap-leads:
	$(PYTHON_ENV) $(PYTHON) scripts/score_target_gap_leads.py --db $(DB) --out data/processed/v2/autoharvest/target_gap_leads/lead_score_report.md --execute

cluster-target-gap-leads:
	$(PYTHON_ENV) $(PYTHON) scripts/cluster_target_gap_leads.py --db $(DB) --out data/processed/v2/autoharvest/target_gap_leads/lead_cluster_report.md --execute

simulate-constraint-relaxation:
	$(PYTHON_ENV) $(PYTHON) scripts/simulate_constraint_relaxation.py --db $(DB) --config config/constraint_decision.yml --out data/processed/v2/autoharvest/target_gap_leads/constraint_relaxation_simulation.md --execute

no-human-lead-dashboard:
	$(PYTHON_ENV) $(PYTHON) scripts/build_no_human_lead_dashboard.py --db $(DB) --out data/processed/v2/autoharvest/target_gap_leads/no_human_lead_dashboard.md

tiny-review-packet:
	$(PYTHON_ENV) $(PYTHON) scripts/build_tiny_review_packet.py --db $(DB) --out-dir data/review/v2/autoharvest/tiny_review_packet_top_50 --limit 50

lead-mode-start:
	$(PYTHON_ENV) $(PYTHON) scripts/run_target_gap_lead_mode_operator.py --db $(DB) --config config/constraint_decision.yml --target-leads 2000 --execute

strict-closeout-and-lead-plan:
	$(MAKE) target-gap-leads-migrate
	$(MAKE) strict-no-credential-closeout
	$(MAKE) convert-failures-to-leads
	$(MAKE) score-target-gap-leads
	$(MAKE) cluster-target-gap-leads
	$(MAKE) simulate-constraint-relaxation
	$(MAKE) no-human-lead-dashboard
	$(MAKE) test
	$(MAKE) validate-v2
	$(MAKE) autoharvest-watchdog
	$(MAKE) public-artifact-check

lead-population-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_target_gap_lead_population.py --db $(DB) --out-dir data/processed/v2/autoharvest/target_gap_leads/population_audit

lead-dedupe:
	$(PYTHON_ENV) $(PYTHON) scripts/dedupe_target_gap_leads.py --db $(DB) --out data/processed/v2/autoharvest/target_gap_leads/lead_dedupe_report.md --execute

lead-date-salvage:
	$(PYTHON_ENV) $(PYTHON) scripts/salvage_missing_dates_from_leads.py --db $(DB) --out data/processed/v2/autoharvest/target_gap_leads/date_salvage_report.md --execute

metadata-only-1955-1976-layer:
	$(PYTHON_ENV) $(PYTHON) scripts/build_metadata_only_1955_1976_layer.py --db $(DB) --out-dir data/processed/v2/autoharvest/metadata_only_1955_1976 --execute

lead-blocker-analysis:
	$(PYTHON_ENV) $(PYTHON) scripts/analyze_lead_blockers.py --db $(DB) --out data/processed/v2/autoharvest/target_gap_leads/lead_blocker_analysis.md

lead-observation-dashboard:
	$(PYTHON_ENV) $(PYTHON) scripts/build_lead_observation_dashboard.py --db $(DB) --out data/processed/v2/autoharvest/target_gap_leads/lead_observation_dashboard.md

lead-mode-start-decision:
	$(PYTHON_ENV) $(PYTHON) scripts/decide_whether_to_start_lead_mode.py --db $(DB) --config config/constraint_decision.yml --out data/processed/v2/autoharvest/target_gap_leads/lead_mode_start_decision.md

source-intelligence-brief:
	$(PYTHON_ENV) $(PYTHON) scripts/build_source_intelligence_brief.py --db $(DB) --out data/processed/v2/autoharvest/target_gap_leads/source_intelligence_brief.md

lead-intelligence-all:
	$(MAKE) lead-population-audit
	$(MAKE) lead-dedupe
	$(MAKE) lead-date-salvage
	$(MAKE) score-target-gap-leads
	$(MAKE) cluster-target-gap-leads
	$(MAKE) metadata-only-1955-1976-layer
	$(MAKE) lead-blocker-analysis
	$(MAKE) lead-observation-dashboard
	$(MAKE) lead-mode-start-decision
	$(MAKE) source-intelligence-brief
	$(MAKE) test
	$(MAKE) validate-v2
	$(MAKE) autoharvest-watchdog
	$(MAKE) public-artifact-check

research-volume-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_research_volume_expansion_v1.py --db $(DB)

research-volume-scheduler:
	$(PYTHON_ENV) $(PYTHON) scripts/build_research_volume_expansion_scheduler.py --db $(DB) --run-id research_volume_expansion_001 --target-new-items 25000 --out data/processed/v2/autoharvest/research_volume/volume_expansion_schedule.csv --report data/processed/v2/autoharvest/research_volume/volume_expansion_schedule.md --execute

research-volume-expand:
	$(PYTHON_ENV) $(PYTHON) scripts/run_research_volume_expansion_operator.py --db $(DB) --run-id research_volume_expansion_001 --target-new-items 25000 --execute

research-volume-dashboard:
	$(PYTHON_ENV) $(PYTHON) scripts/build_research_volume_dashboard.py --db $(DB) --run-id research_volume_expansion_001 --out data/processed/v2/autoharvest/research_volume/research_volume_dashboard.md

research-volume-all:
	$(MAKE) research-volume-migrate
	$(MAKE) lead-population-audit
	$(MAKE) lead-dedupe
	$(MAKE) cluster-target-gap-leads
	$(MAKE) research-volume-scheduler
	$(MAKE) research-volume-expand
	$(MAKE) research-volume-dashboard
	$(MAKE) test
	$(MAKE) validate-v2
	$(MAKE) autoharvest-watchdog
	$(MAKE) public-artifact-check

release-freeze-inputs:
	$(PYTHON_ENV) $(PYTHON) scripts/freeze_release_inputs.py --db $(DB) --out-dir data/processed/v2/release_freeze --execute

release-coverage-1926-2011:
	$(PYTHON_ENV) $(PYTHON) scripts/build_1926_2011_release_coverage.py --db $(DB) --freeze data/processed/v2/release_freeze/freeze_state.json --out-dir data/processed/v2/release_coverage_1926_2011 --execute

release-bounded-patch-plan:
	$(PYTHON_ENV) $(PYTHON) scripts/build_bounded_patch_plan_1926_2011.py --db $(DB) --coverage-dir data/processed/v2/release_coverage_1926_2011 --out data/interim/collection_plans/bounded_patch_plan_1926_2011.csv --report data/processed/v2/release_coverage_1926_2011/bounded_patch_plan_1926_2011.md --max-patch-items 3000 --execute

release-layers-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_release_layers_v1.py --db $(DB)

release-apply-bounded-patch:
	$(PYTHON_ENV) $(PYTHON) scripts/apply_bounded_patch_to_release_layers.py --db $(DB) --patch-plan data/interim/collection_plans/bounded_patch_plan_1926_2011.csv --run-id final_patch_1926_2011_001 --execute

release-final-map-layers:
	$(PYTHON_ENV) $(PYTHON) scripts/build_final_map_layers.py --db $(DB) --frontend-map public/data/frontend-data.json --out-dir data/processed/v2/final_map_layers --execute

release-redirects-migrate:
	$(PYTHON_ENV) $(PYTHON) scripts/migrate_redirect_registry_v1.py --db $(DB)

release-build-redirects:
	$(PYTHON_ENV) $(PYTHON) scripts/build_redirect_registry.py --db $(DB) --out-dir data/processed/v2/redirects --execute

release-validate-redirects:
	$(PYTHON_ENV) $(PYTHON) scripts/validate_redirect_registry.py --db $(DB) --redirect-dir data/processed/v2/redirects --out data/processed/v2/redirects/redirect_validation_report.md

release-build-package:
	$(PYTHON_ENV) $(PYTHON) scripts/build_final_frontend_release_package.py --db $(DB) --map-layers data/processed/v2/final_map_layers --redirect-dir data/processed/v2/redirects --coverage-dir data/processed/v2/release_coverage_1926_2011 --out-dir data/processed/v2/final_release_package --execute

release-final-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/final_release_audit.py --db $(DB) --package-dir data/processed/v2/final_release_package --redirect-dir data/processed/v2/redirects --out-dir data/processed/v2/final_release_audit

release-dashboard:
	$(PYTHON_ENV) $(PYTHON) scripts/build_final_release_dashboard.py --audit-dir data/processed/v2/final_release_audit --coverage-dir data/processed/v2/release_coverage_1926_2011 --map-dir data/processed/v2/final_map_layers --redirect-dir data/processed/v2/redirects --out data/processed/v2/final_release_dashboard.md

release-sprint-all:
	$(MAKE) release-freeze-inputs
	$(MAKE) release-coverage-1926-2011
	$(MAKE) release-bounded-patch-plan
	$(MAKE) release-layers-migrate
	$(MAKE) release-apply-bounded-patch
	$(MAKE) release-final-map-layers
	$(MAKE) release-redirects-migrate
	$(MAKE) release-build-redirects
	$(MAKE) release-validate-redirects
	$(MAKE) release-build-package
	$(MAKE) release-final-audit
	$(MAKE) release-dashboard
	$(MAKE) test
	$(MAKE) validate-v2
	$(MAKE) public-artifact-check
	$(MAKE) autoharvest-watchdog

release-apply-package-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/apply_final_release_package.py --package-dir data/processed/v2/final_release_package --dry-run

release-apply-package:
	$(PYTHON_ENV) $(PYTHON) scripts/apply_final_release_package.py --package-dir data/processed/v2/final_release_package --execute

.PHONY: frontend-count-contract frontend-display-audit frontend-integrate-sidecars frontend-release-cards frontend-release-charts frontend-release-contract-validate frontend-smoke-tests post-release-site-audit major-phase-report post-release-site-integration-all

frontend-count-contract:
	$(PYTHON_ENV) $(PYTHON) scripts/build_frontend_count_contract.py --db $(DB) --frontend-data public/data/frontend-data.json --release-package data/processed/v2/final_release_package --coverage-dir data/processed/v2/release_coverage_1926_2011 --map-dir data/processed/v2/final_map_layers --redirect-dir data/processed/v2/redirects --out public/data/release-count-contract.json --report data/processed/v2/post_release_site_integration/count_contract_report.md --execute

frontend-display-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_frontend_display_contract.py --repo-root . --count-contract public/data/release-count-contract.json --out-dir data/processed/v2/post_release_site_integration/frontend_display_audit

frontend-integrate-sidecars:
	$(PYTHON_ENV) $(PYTHON) scripts/integrate_release_sidecars_into_frontend.py --repo-root . --release-package data/processed/v2/final_release_package --count-contract public/data/release-count-contract.json --execute

frontend-release-cards:
	$(PYTHON_ENV) $(PYTHON) scripts/generate_release_cards.py --db $(DB) --release-package data/processed/v2/final_release_package --redirect-dir data/processed/v2/redirects --out public/data/release-cards.json --report data/processed/v2/post_release_site_integration/release_cards_report.md --execute

frontend-release-charts:
	$(PYTHON_ENV) $(PYTHON) scripts/build_release_chart_data.py --db $(DB) --count-contract public/data/release-count-contract.json --coverage-dir data/processed/v2/release_coverage_1926_2011 --map-dir data/processed/v2/final_map_layers --release-package data/processed/v2/final_release_package --out public/data/release-charts.json --report data/processed/v2/post_release_site_integration/release_charts_report.md --execute

frontend-release-contract-validate:
	$(PYTHON_ENV) $(PYTHON) scripts/validate_frontend_release_contracts.py --repo-root . --count-contract public/data/release-count-contract.json --cards public/data/release-cards.json --charts public/data/release-charts.json --package-dir data/processed/v2/final_release_package --out data/processed/v2/post_release_site_integration/frontend_release_contract_validation.md

frontend-smoke-tests:
	$(PYTHON_ENV) $(PYTHON) scripts/run_frontend_smoke_tests.py --repo-root . --out-dir data/processed/v2/post_release_site_integration/smoke_tests --execute

post-release-site-audit:
	$(PYTHON_ENV) $(PYTHON) scripts/post_release_site_audit.py --repo-root . --db $(DB) --count-contract public/data/release-count-contract.json --cards public/data/release-cards.json --charts public/data/release-charts.json --final-audit data/processed/v2/final_release_audit --out-dir data/processed/v2/post_release_site_integration/final_site_audit --execute

major-phase-report:
	$(PYTHON_ENV) $(PYTHON) scripts/build_major_phase_report.py --repo-root . --db $(DB) --out docs/release/MAJOR_PHASE_RELEASE_REPORT.md --also-out data/processed/v2/post_release_site_integration/major_phase_release_report.md --execute

post-release-site-integration-all:
	$(MAKE) frontend-count-contract
	$(MAKE) frontend-display-audit
	$(MAKE) frontend-integrate-sidecars
	$(MAKE) frontend-release-cards
	$(MAKE) frontend-release-charts
	$(MAKE) frontend-release-contract-validate
	$(MAKE) frontend-smoke-tests
	$(MAKE) post-release-site-audit
	$(MAKE) major-phase-report
	$(MAKE) test
	$(MAKE) validate-v2
	$(MAKE) public-artifact-check
	$(MAKE) autoharvest-watchdog

.PHONY: paper-freeze paper-stats paper-figures paper-audit-sample paper-check

paper-freeze:
	$(PYTHON_ENV) $(PYTHON) scripts/paper/freeze_paper_corpus.py --config config/paper_hss_freeze.yaml --execute

paper-stats:
	$(PYTHON_ENV) $(PYTHON) scripts/paper/generate_paper_stats.py --config config/paper_hss_freeze.yaml --write-docs

paper-figures: paper-stats
	$(PYTHON_ENV) $(PYTHON) scripts/paper/generate_paper_figures.py --config config/paper_hss_freeze.yaml

paper-audit-sample:
	$(PYTHON_ENV) $(PYTHON) scripts/paper/generate_audit_sample.py --config config/paper_hss_freeze.yaml

paper-check: paper-freeze paper-stats paper-figures paper-audit-sample
	$(PYTHON_ENV) $(PYTHON) scripts/paper/validate_paper_release.py --config config/paper_hss_freeze.yaml
