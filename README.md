# Humanoid Supernatural Beings in Australian Public Texts

This repository supports the project **Humanoid Supernatural Beings in Australian Public Texts: Semantic Change, Public Discourse, and Search Attention from 1842 to the Present**.

The first engineering pass builds a reproducible data-collection foundation. It creates a SQLite schema, seed lexicons, source definitions, query plans, conservative import/classification utilities, validation checks, export scripts, and documentation. It does **not** scrape aggressively, collect restricted materials, or write the final analysis.

## Scope

The project is Australia-only and studies public textual representations of humanoid or humanoid-adjacent supernatural beings. It is not a generic monster database. Indigenous cultural knowledge is treated carefully by coding source voice, publicness, mediation, and ethics flags rather than flattening material into a cryptid category.

Do not collect secret/sacred, restricted, unpublished, community-controlled, or non-public materials. Public catalogue metadata can help identify sources for review, but it is not permission to extract restricted cultural knowledge.

## Setup

Use Python 3.11 or newer. Install dependencies when needed:

```sh
python3 -m pip install -r requirements.txt
```

The core workflow writes `data/processed/australian_humanoid_figures.sqlite`.

```sh
make init
make seed
make queries
make validate
make export
make test
```

The acceptance shortcut is:

```sh
make init seed queries validate export test
```

## Commands

`make init` creates the SQLite database and all tables/indexes.

`make seed` reads `config/sources.yml` and `config/lexicon.yml`, then inserts or updates sources, figures, and aliases. Core terms, validation-queue terms, and excluded/control terms are all seeded with explicit include status.

`make queries` reads `config/queries.yml` and `config/noise_rules.yml`, then inserts planned query rows. High-noise terms such as `Yahoo`, `Mimi`, `Mamu`, and `Hairy Man` are constrained and never emitted as bare queries.

`make trove-template`, `make trends-template`, and `make pageviews-template` write safe planning CSVs under `data/interim/`. These are stubs/templates only.

`make collect-public-round` runs a small public-only seed collection round. It retrieves Wikimedia public summaries, one verified ABC News public page, and public metadata leads for early NLA/Trove items. Trove/NLA leads are marked as metadata leads unless full text is manually/API-key verified.

`make locations` seeds a small reviewed gazetteer and attaches rule-based place/region matches to imported records. Location matches are evidence for human review, not final geocoding truth.

`python3 scripts/import_manual_csv.py path/to/records.csv` imports manually downloaded or search-exported public records. The CSV must include:

```text
source_name, query_string, external_id, title, publication, author, date_published, url, snippet, raw_text
```

Raw text is saved under `data/raw/text/`, records are inserted into SQLite, years are parsed where possible, and initial rule-based coding is added for human review.

`make validate` writes `data/processed/validation_report.md`.

`make export` writes human-review CSVs under `data/exports/`:

- `records_review.csv`
- `figures_aliases.csv`
- `query_plan.csv`
- `attention_series.csv`
- `record_locations.csv`

## What This Does Not Do

This pass does not perform live Trove scraping, require API credentials, run Google Trends collection, collect Wikimedia pageviews, or infer final interpretive categories. Rule-based classification is triage only. Every imported record still requires human review.
