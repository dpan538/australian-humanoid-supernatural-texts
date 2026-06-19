# Humanoid Supernatural Beings in Australian Public Texts

This repository supports the project **Humanoid Supernatural Beings in Australian Public Texts: Semantic Change, Public Discourse, and Search Attention from 1842 to the Present**.

The first engineering pass builds a reproducible data-collection foundation. It creates a SQLite schema, seed lexicons, source definitions, query plans, conservative import/classification utilities, validation checks, export scripts, and documentation. It does **not** scrape aggressively, collect restricted materials, or write the final analysis.

Repository: <https://github.com/dpan538/australian-humanoid-supernatural-texts>

## Scope

The project is Australia-only and studies public textual representations of humanoid or humanoid-adjacent supernatural beings. It is not a generic monster database. Indigenous cultural knowledge is treated carefully by coding source voice, publicness, mediation, and ethics flags rather than flattening material into a cryptid category.

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

## Commands

`make init` creates the SQLite database and all tables/indexes.

`make seed` reads `config/sources.yml` and `config/lexicon.yml`, then inserts or updates sources, figures, and aliases. Core terms, validation-queue terms, and excluded/control terms are all seeded with explicit include status.

`make queries` reads `config/queries.yml` and `config/noise_rules.yml`, then inserts planned query rows. High-noise terms such as `Yahoo`, `Mimi`, `Mamu`, and `Hairy Man` are constrained and never emitted as bare queries.

`make trove-template`, `make trends-template`, and `make pageviews-template` write safe planning CSVs under `data/interim/`. These are stubs/templates only.

`make collect-public-round` runs a small public-only seed collection round. It retrieves Wikimedia public summaries, one verified ABC News public page, and public metadata leads for early NLA/Trove items. Trove/NLA leads are marked as metadata leads unless full text is manually/API-key verified.

`make plan-public-round-002` writes a broader second-round public-source lead plan and location-review queue without making network requests or inserting records. It is the review step before any expanded live collection. The planner is configured by `config/round_002.yml`, filters blocked high-noise or non-public source rows by default, preserves per-location evidence in `locations_json`, and can fail before writing outputs with `--fail-on-blocked`.

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

`make export-frontend` writes `public/data/frontend-data.json`, the static data contract used by the Next.js archive-terminal interface. `make frontend-build` runs the production build intended for Vercel.

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

This pass does not perform live Trove scraping, require API credentials, run Google Trends collection, collect Wikimedia pageviews, or infer final interpretive categories. Rule-based classification is triage only. Every imported record still requires human review.

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
