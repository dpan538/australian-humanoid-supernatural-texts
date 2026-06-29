# Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters

A typed, provenance-aware public research archive for tracing how humanoid or humanoid-adjacent supernatural figures appear in Australian public texts.

The project documents source-grounded public records: alleged encounters, apparition accounts, ghost legends, local legends, traditional and spirit-person narratives, descriptive belief records, and later retellings. It does not verify supernatural claims. Inclusion means that a public source or public metadata record exists and can be cited, reviewed, or linked.

The public interface is a research display system, not a proof-of-existence database and not a generic monster catalogue.

Repository: <https://github.com/dpan538/australian-humanoid-supernatural-texts>

Public site: <https://ausfigures.com>

Canonical production origin: <https://ausfigures.com>

Homepage route: <https://ausfigures.com/>

## What this project is

This archive studies public textual representation, not biological or supernatural truth. The top-level object is a narrative or source-grounded public record. Bounded encounter events are one subtype, not the whole archive.

The project is:

- Australia-only;
- based on public records and public metadata;
- typed by narrative role, source family, publicness, date, and location evidence;
- built for provenance review, ethics review, reclassification, and research extension;
- designed as a public archive-terminal interface for map, density, dashboard, source, and about views.

Earlier repository history used the working title **Humanoid Supernatural Beings in Australian Public Texts: Semantic Change, Public Discourse, and Search Attention from 1842 to the Present**. That legacy title remains in repository history for provenance, but the current project title and data model are the archive title above.

## What this project is not

This project is not:

- proof that any supernatural entity exists;
- a complete census of Australian folklore;
- a habitat or population map;
- an authoritative Indigenous knowledge repository;
- permission to reproduce restricted cultural material;
- a tourism or haunted-place directory.

Public discoverability is not treated as unrestricted permission. Indigenous-related records require particular care around terminology, publicness, source voice, sensitivity, and display mode.

## Public interface

The frontend is a restrained archive-terminal research display. It uses a dark terminal palette, source and narrative typing, state-outline geography, dense dashboard panels, source registers, and public-data status modules.

Pages:

- `https://ausfigures.com/`: homepage index map for verified mapped public records only. Each map flag represents one public record with a verified display location.
- `https://ausfigures.com/dashboard`: broad public-corpus overview across time, narrative, source, and mapped-record aggregates.
- `https://ausfigures.com/map`: map route alias for the same verified mapped public records view.
- `https://ausfigures.com/density`: compressed source/query/figure density fields for comparing corpus signals.
- `https://ausfigures.com/source`: two-pane source register showing source-family rollups and registered public source organisations.
- `https://ausfigures.com/about`: research-positioning page explaining scope, method, source policy, mapping limits, and ethics.

Dashboard and Density use the broader public corpus. Map uses only records with verified display coordinates.

## Data model

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

The static frontend reads public export data from the generated JSON contract. Public record counts, mapped counts, source summaries, and map flags should derive from that frontend data export, not from hard-coded display values.

## Source and ethics policy

Preferred source families include archives, libraries, newspapers, public-domain books, institutional pages, public repositories, public catalogue metadata, and community-controlled public materials.

Tourism pages and unsourced paranormal aggregators may be useful as discovery leads, but they are not treated as primary evidence without stronger source support.

Public catalogue metadata is not permission to extract restricted content. Records involving Aboriginal and Torres Strait Islander peoples, communities, or culturally specific figures require stronger caution around terminology, publicness, cultural sensitivity, and display mode. Sensitive public material may be summary-only or suppressed from public display.

See also `docs/release/SOURCE_POLICY.md`.

## Map and location policy

The public map shows verified display locations for public records. A map flag is not proof of an event, a habitat, a population distribution, or cultural authority.

One public record can produce zero or one public map flag. Publication locations, archive custody locations, source institution addresses, author residences, inferred state-only locations, and broad cultural regions without display clearance are not valid public map flags.

See also `docs/release/MAP_ELIGIBILITY.md`.

## Running locally

Use Python 3.11 or newer for data utilities:

```sh
python3 -m pip install -r requirements.txt
```

The visual frontend uses Next.js and reads a static JSON export from the SQLite database:

```sh
npm ci
make export-frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Build the frontend:

```sh
npm run build
```

## Data workflow

The core workflow writes `data/processed/australian_humanoid_figures.sqlite`.

```sh
make init
make seed
make queries
make validate
make export
make test
```

Acceptance shortcut:

```sh
make init seed queries validate export test
```

Non-destructive V2 workflow:

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

Useful collection and review commands:

- `make snapshot-legacy` freezes the current flat-record corpus under `data/releases/legacy_985/` with checksums and a release README.
- `make migrate-v2` creates the additive V2 schema and maps every legacy record through `legacy_record_mappings`.
- `make collect-v2-batch` stages V2 collection candidates. Unresolved leads, metadata-only pointers, controls, exclusions, duplicates, and inaccessible snippets do not count as accepted source items.
- `make collect-v2-3000` starts the strict-geography expansion path. A candidate counts only when it has a stable public source, substantive evidence summary, source label, ethics status, and verified latitude/longitude tied to a named Australian place.
- `make export-v2` writes normalized review exports under `data/exports/v2/` and `public/data/frontend-data/v2.json`.
- `make audit-v2` writes corpus status, diversity, temporal, geographic, ethics, cleaning, dedupe, and collection-progress reports under `data/processed/v2/`.
- `make export-frontend` writes `public/data/frontend-data.json`, the static legacy-compatible frontend data contract, and runs the normalized V2 export through `scripts/export_v2.py`.
- `make frontend-build` runs the production build intended for deployment.

Manual CSV import:

```sh
python3 scripts/import_manual_csv.py path/to/records.csv
```

Expected CSV columns:

```text
source_name, query_string, external_id, title, publication, author, date_published, url, snippet, raw_text
```

Raw text is saved under `data/raw/text/`, records are inserted into SQLite, years are parsed where possible, and initial rule-based coding is added for human review.

See also:

- `docs/research/METHODS_V2.md`
- `docs/research/SCOPE_V2.md`
- `docs/research/FRONTEND_DATA_CONTRACT_V2.md`
- `docs/release/VERCEL_DEPLOYMENT.md`
- `docs/release/LAUNCH_CHECKLIST.md`

## Public web discovery files

The production site publishes restrained public-archive discovery files:

- `https://ausfigures.com/robots.txt`
- `https://ausfigures.com/sitemap.xml`
- `https://ausfigures.com/llms.txt`

These files describe only public routes and public launch guidance. They are not security boundaries and should not be used to hide restricted, sensitive, unpublished, or internal material.

## Repository structure

```text
app/                         Next.js app routes and global styling
components/                  Frontend views, overlays, source/map/dashboard UI
config/                      Source, lexicon, route, query, and collection config
data/                        Local database, exports, interim files, reports
docs/research/               Methods, scope, and frontend data-contract notes
lib/                         Shared frontend data/types/map utilities
public/data/                 Static frontend data export
scripts/                     Database, export, collection, audit, and repair utilities
```

## Citation

Please cite the project if you use the repository, database structure, query plan, exported review tables, or public-facing interface in research, teaching, writing, or design discussion. When citing a specific export, include the export filename and access date.

APA 7:

```text
Pan, D. (2026). Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters [Research database and public archive interface]. GitHub. https://github.com/dpan538/australian-humanoid-supernatural-texts
```

MLA:

```text
Pan, Dai. Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters. GitHub, 2026, https://github.com/dpan538/australian-humanoid-supernatural-texts.
```

Chicago:

```text
Pan, Dai. 2026. Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters. Research database and public archive interface. GitHub. https://github.com/dpan538/australian-humanoid-supernatural-texts.
```

BibTeX:

```bibtex
@misc{pan2026australianpublictextarchive,
  author = {Pan, Dai},
  title = {Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters},
  year = {2026},
  howpublished = {Research database and public archive interface, GitHub repository},
  url = {https://github.com/dpan538/australian-humanoid-supernatural-texts},
  note = {Cite export filename and access date when using a specific dataset export}
}
```

Legacy working titles are preserved in repository history but should not be used as the primary citation title for current V2 work.

## Licensing

This repository uses a split license:

- MIT License for data-engineering scripts, database utilities, configuration templates, and non-visual infrastructure code. See `LICENSE-MIT.md`.
- Custom visual-interface license for the archive-terminal interface concept, dashboard/map/density/source page architecture, interaction design, layout composition, and frontend visual implementation. See `LICENSE-VISUAL.md`.
- Third-party source texts, catalogue records, web pages, images, and map data retain their original rights.

GitHub may show multiple or unknown licenses because of the custom visual-interface license. Do not remove the visual license merely to simplify the GitHub sidebar.

See also `docs/LICENSING.md`.
