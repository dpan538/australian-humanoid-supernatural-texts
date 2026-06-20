# Humanoid Supernatural Beings in Australian Public Texts

This repository supports the project **Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters**.

Earlier repository history used the working title **Humanoid Supernatural Beings in Australian Public Texts: Semantic Change, Public Discourse, and Search Attention from 1842 to the Present**. That legacy framing is preserved for provenance, but V2 adopts a typed multi-corpus narrative archive model.

Recommended description:

> A typed, provenance-aware, ethically constrained archive of public Australian texts about supernatural or anomalous humanoid encounters, apparitions, rumours, legends, traditional narratives, and their later retellings.

The first engineering pass builds a reproducible data-collection foundation. It creates a SQLite schema, seed lexicons, source definitions, query plans, conservative import/classification utilities, validation checks, export scripts, and documentation. It does **not** scrape aggressively, collect restricted materials, or write the final analysis.

Repository: <https://github.com/dpan538/australian-humanoid-supernatural-texts>

## Scope

The project is Australia-only and studies public textual narratives and records about humanoid or humanoid-adjacent supernatural or anomalous figures. It is not a generic monster database. Indigenous cultural knowledge is treated carefully by coding source voice, publicness, mediation, source/community terminology, display mode, and ethics status rather than flattening material into a cryptid category.

The governing research question is:

> How have supernatural or anomalous humanoid figures been encountered, narrated, localised, named, transmitted, and reinterpreted in Australian public texts?

Do not collect secret/sacred, restricted, unpublished, community-controlled, or non-public materials. Public catalogue metadata can help identify sources for review, but it is not permission to extract restricted cultural knowledge.

## Setup

Use Python 3.11 or newer. Install dependencies when needed:

```sh
python3 -m pip install -r requirements.txt
```

The visual frontend uses Next.js and reads a static JSON export from the SQLite database:

```sh
npm install
make export-frontend
npm run dev
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

## V2 Normalized Narrative Archive

V2 keeps the legacy `records` table intact and adds normalized tables for:

- `source_items`
- `narrative_units`
- `encounter_events`
- `entity_concepts`
- `entity_labels`
- `narrative_source_links`
- `narrative_relations`
- `narrative_locations`
- `reviews`
- `leads`
- `exclusions`
- `legacy_record_mappings`

The top-level research object is `narrative_unit`. An encounter event is an optional subtype, not the universal record model.

Run the non-destructive V2 workflow:

```sh
make snapshot-legacy
make migrate-v2
make collect-v2-dry-run
make export-v2
make audit-v2
make validate-v2
make export-frontend
make test
make frontend-build
```

`make snapshot-legacy` freezes the current flat-record corpus under `data/releases/legacy_985/` with checksums and a release README.

`make migrate-v2` creates the additive V2 schema and maps every legacy record through `legacy_record_mappings`.

`make collect-v2-batch` stages V2 collection candidates. It does not count unresolved leads, metadata-only pointers, controls, exclusions, duplicates, or inaccessible snippets toward the 500 accepted-source target.

`make export-v2` writes normalized review exports under `data/exports/v2/` and `public/data/frontend-data/v2.json`.

`make audit-v2` writes V2 corpus status, diversity, temporal, geographic, ethics, cleaning, dedupe, and collection-progress reports under `data/processed/v2/`.

See `docs/research/METHODS_V2.md`, `docs/research/SCOPE_V2.md`, and `docs/research/FRONTEND_DATA_CONTRACT_V2.md`.

## Commands

`make init` creates the SQLite database and all tables/indexes.

`make seed` reads `config/sources.yml` and `config/lexicon.yml`, then inserts or updates sources, figures, and aliases. Core terms, validation-queue terms, and excluded/control terms are all seeded with explicit include status.

`make queries` reads `config/queries.yml` and `config/noise_rules.yml`, then inserts planned query rows. High-noise terms such as `Yahoo`, `Mimi`, `Mamu`, and `Hairy Man` are constrained and never emitted as bare queries.

`make trove-template`, `make trends-template`, and `make pageviews-template` write safe planning CSVs under `data/interim/`. These are stubs/templates only.

`make collect-public-round` runs a small public-only seed collection round. It retrieves Wikimedia public summaries, one verified ABC News public page, and public metadata leads for early NLA/Trove items. Trove/NLA leads are marked as metadata leads unless full text is manually/API-key verified.

`make collect-ayr-records` runs the first expanded live collection pass against public Australian Yowie Research report pages. It targets 200 new `raw_public_web_card_ready` records. A page is inserted only when it has enough information for a frontend record card: year, title/figure, public URL/source, Australian state or territory, and an objective display summary. Search leads, query plans, and pages missing those fields are not records.

`make plan-public-round-002` writes a broader second-round public-source lead plan and location-review queue without making network requests or inserting records. It is the review step before any expanded live collection. The planner is configured by `config/round_002.yml`, filters blocked high-noise or non-public source rows by default, deduplicates repeated query/source/date leads into `related_lead_ids`, preserves per-location evidence in `locations_json`, and can fail before writing outputs with `--fail-on-blocked`. It also writes run metadata and a SHA256 manifest for reproducibility.

`make audit-round-002` writes `data/processed/public_round_002_coverage_audit.md`, summarising planned lead coverage by date band, location hint, source mix, figure mix, and the recommended next 500-record collection quotas. Planned leads are not records and are not exported to the frontend as record cards.

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

`make export-frontend` writes `public/data/frontend-data.json`, the static legacy-compatible data contract used by the Next.js archive-terminal interface, and also writes the normalized V2 contract through `scripts/export_v2.py`. `make frontend-build` runs the production build intended for Vercel.

`make export-frontend` also runs a deterministic 50-record card-readiness and map-coverage audit at `data/processed/v2/frontend_record_card_sample_audit.md`. Use this after collection or migration work to confirm that records have enough fields for the overlay card and that every frontend record has an individual clickable map flag. State-level or broad locations use deterministic in-state display placement and must not be interpreted as precise event coordinates.

## Public Interface Design

The public interface is a research display for public Australian textual records, not a generic folklore catalogue or a claim-making database. It uses a restrained archive-terminal visual language: black, white, grey, small amounts of fluorescent green and blue-grey, ASCII-like texture, state-outline mapping, density fields, and compressed dashboard modules.

The display is organised around four stable pages:

- `Map`: a state-and-territory outline view for regional distribution and verified/broad location signals.
- `Dashboard`: the highest-density overview, combining record counts, query/source structure, figure signals, and region distribution.
- `Density`: a compressed signal field for source/query/figure density without full record detail.
- `Source`: a source and ethics register showing publicness, source type, and repository/citation context.

Design cautions:

- Visual mystery is used to express archival uncertainty, not to obscure research provenance.
- Uncertain or mediated records should remain visibly reviewable rather than being flattened into final facts.
- Publicness, source voice, mediation, ethics flags, and location precision are first-order display data.
- The interface should not present Indigenous cultural knowledge as cryptid inventory, and public metadata must not be treated as permission to extract restricted cultural material.
- The visual system and frontend page architecture are part of the project identity; see `LICENSE-VISUAL.md` before reusing interface concepts, layouts, or frontend implementation.

## What This Does Not Do

This pass does not perform live Trove scraping without an API key, require API credentials, run Google Trends collection, collect Wikimedia pageviews, or infer final interpretive categories. Rule-based classification is triage only. Every imported record still requires human review.

Planned leads are never accepted V2 source items. A row may enter the legacy `records` table only after it has enough public information to render a review card and pass the publicness/location gate. A V2 candidate counts toward the +500 target only after it passes the stricter accepted-source gate.

## Citation

Please cite the project if you use the repository, database structure, query plan, exported review tables, or public-facing interface in research, teaching, writing, or design discussion. When citing a specific export, include the export filename and access date.

APA 7:

```text
Pan, D. (2026). Humanoid Supernatural Beings in Australian Public Texts: Semantic Change, Public Discourse, and Search Attention from 1842 to the Present [Research database and public archive interface]. GitHub. https://github.com/dpan538/australian-humanoid-supernatural-texts
```

MLA:

```text
Pan, Dai. Humanoid Supernatural Beings in Australian Public Texts: Semantic Change, Public Discourse, and Search Attention from 1842 to the Present. GitHub, 2026, https://github.com/dpan538/australian-humanoid-supernatural-texts.
```

Chicago:

```text
Pan, Dai. 2026. Humanoid Supernatural Beings in Australian Public Texts: Semantic Change, Public Discourse, and Search Attention from 1842 to the Present. Research database and public archive interface. GitHub. https://github.com/dpan538/australian-humanoid-supernatural-texts.
```

BibTeX:

```bibtex
@misc{pan2026australianhumanoid,
  author = {Pan, Dai},
  title = {Humanoid Supernatural Beings in Australian Public Texts: Semantic Change, Public Discourse, and Search Attention from 1842 to the Present},
  year = {2026},
  howpublished = {Research database and public archive interface, GitHub repository},
  url = {https://github.com/dpan538/australian-humanoid-supernatural-texts},
  note = {Cite export filename and access date when using a specific dataset export}
}
```

## Licensing

This repository uses a split license model.

- Original research information, query definitions, documentation, and exported review tables may be quoted, cited, and reused with attribution to Dai Pan, subject to the rights and restrictions of the original public source materials.
- Data-engineering scripts, database utilities, and non-visual infrastructure code are available under the MIT license in `LICENSE-MIT.md`.
- The public interface concept, ASCII/terminal visual system, dashboard/map/density/source page architecture, interaction design, layout composition, and frontend visual implementation are governed by `LICENSE-VISUAL.md`. They may be discussed, cited, and linked, but the visual architecture and frontend implementation may not be copied into a direct clone or substantially similar interface without written permission.

Source texts, catalogue records, web pages, and other third-party materials retain their original rights. This project does not relicense third-party source content.
