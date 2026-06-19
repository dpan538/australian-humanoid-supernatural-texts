PYTHON ?= python3
PYTHON_ENV ?= PYTHONDONTWRITEBYTECODE=1
DB ?= data/processed/australian_humanoid_figures.sqlite

.PHONY: init seed queries trove-template trends-template pageviews-template collect-public-round locations validate export export-frontend dedupe test frontend-build

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

locations:
	$(PYTHON_ENV) $(PYTHON) scripts/enrich_locations.py --db $(DB)

validate:
	$(PYTHON_ENV) $(PYTHON) scripts/validate_records.py --db $(DB)

export:
	$(PYTHON_ENV) $(PYTHON) scripts/export_dataset.py --db $(DB)

export-frontend:
	$(PYTHON_ENV) $(PYTHON) scripts/export_frontend_json.py --db $(DB)

dedupe:
	$(PYTHON_ENV) $(PYTHON) scripts/run_dedupe.py --db $(DB)

test:
	$(PYTHON_ENV) $(PYTHON) scripts/run_tests.py

frontend-build:
	npm run build
