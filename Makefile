PYTHON ?= python3
PYTHON_ENV ?= PYTHONDONTWRITEBYTECODE=1
DB ?= data/processed/australian_humanoid_figures.sqlite

.PHONY: init seed queries trove-template trends-template pageviews-template collect-public-round collect-ayr-records plan-public-round-002 audit-round-002 locations validate export export-frontend frontend-audit dedupe test frontend-build snapshot-legacy migrate-v2 classify-legacy clean-v2 dedupe-v2 audit-v2 collect-v2-dry-run collect-v2-batch collect-v2-500 collect-v2-3000 export-v2 validate-v2

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

classify-legacy: migrate-v2

clean-v2: migrate-v2

dedupe-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/run_dedupe.py --db $(DB)

audit-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/audit_v2.py --db $(DB)

collect-v2-dry-run:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_v2_batch.py --db $(DB) --run-id v2_collection_batch_001 --trove-leads --limit 50

collect-v2-batch:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_v2_batch.py --db $(DB) --run-id v2_collection_batch_001 --trove-leads --limit 50

collect-v2-500:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_v2_batch.py --db $(DB) --run-id v2_collection_batch_001 --trove-leads --limit 50

collect-v2-3000:
	$(PYTHON_ENV) $(PYTHON) scripts/collect_v2_batch.py --db $(DB) --run-id strict_geo_collection_3000_batch_001 --trove-leads --limit 50 --strict-geo-only --target 3000 --report data/processed/v2/collection_3000_strict_geo_progress.md

export-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/export_v2.py --db $(DB)

validate-v2:
	$(PYTHON_ENV) $(PYTHON) scripts/validate_v2.py --db $(DB)
