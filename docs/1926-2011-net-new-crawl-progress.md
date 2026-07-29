# 1926-2011 Net-New Crawl Progress

Generated: 2026-06-30

This document corrects the target metric: the working target is **+4000 net-new records**, not total records crossing 4000. All rows below are stage-only localhost candidates unless explicitly promoted later by human review.

## Current Position

Baseline used for this round:

- `public/data/frontend-data.live-crawl.json`
- Baseline totals: `3897 records / 1206 mapped`

Current localhost experimental overlay:

- `public/data/frontend-data.gap-public-web.json`
- Current totals: `4427 records / 1668 mapped`
- Net-new from baseline: `+530 records / +462 mapped`
- Remaining to +4000 net-new records: `3470 records`
- Remaining to 2500 mapped total: `832 mapped records`

Production data was not modified:

- `public/data/frontend-data.json` remains the production export.
- No candidates were imported into the SQLite database.
- No git staging, commit, or push was performed.

## Source Yield Summary

| source family | raw/accepted signal | net-new records in overlay | net-new mapped | notes |
|---|---:|---:|---:|---|
| ABC public search, strict-cleaned | 42 strict accepted across two rounds | 42 | 24 | High precision but now low yield. Round 012a produced only 1 strict accepted row. |
| AYR public Yowie map | 1024 parsed markers; 825 accepted post-1926 | 351 | 351 | High mapped yield, but 533 candidate/base duplicates removed in combined overlay. |
| AYR state report indexes | 626 parsed links; 613 accepted post-1926 | 21 | 8 | Mostly overlaps AYR map/base; useful as coverage audit, not a major net-new source. |
| HauntedPlaces Australia directory | 78 parsed markers; 78 accepted | 78 | 78 | Clean mapped directory source, but undated and should not feed annual trend. |
| Open Library public books metadata | 232 raw rows in strict round017; 33 accepted | 33 | 1 | Useful for public-text year coverage, mostly unmapped, not a scale route. |
| Wikidata public entity metadata | 48 entities in strictest round023; 5 accepted | 5 | 0 | Clean cross-source entity metadata only; undated and low yield. |
| AYR public site via Common Crawl discovery | 106 current pages fetched in round024a | 0 | 0 | All fetched pages were duplicate against current overlay, confirming AYR public site is already covered. |
| Prior public-web leads strict conversion | 687 prior leads reviewed in stricter round025 | 0 | 0 | Stricter title/URL ghost-term rule blocked navigation-contaminated leads. |
| Combined stage overlay | 1063 unique accepted candidate rows loaded | 530 | 462 | Dedupe removes repeated URL/place rows before overlay. |

## Evidence By Year Bucket

| year bucket | added records | added mapped | main source paths |
|---|---:|---:|---|
| 1926-1945 | 9 | 9 | AYR map/state |
| 1946-1969 | 7 | 5 | AYR map/state and Open Library |
| 1970-1990 | 115 | 108 | AYR map/state and Open Library |
| 1991-2011 | 166 | 132 | AYR map/state, ABC, and Open Library |
| 2012-2026 | 150 | 130 | AYR, ABC |
| undated | 83 | 78 | HauntedPlaces directory and Wikidata |

## Important Files

Candidate CSVs:

- `data/interim/gap_probe_1926_2011/abc_public_search/abc_public_search_round011_abc_place_expanded_strict_candidates.csv`
- `data/interim/gap_probe_1926_2011/abc_public_search/abc_public_search_round012a_abc_more_pages_20q_strict_candidates.csv`
- `data/interim/gap_probe_1926_2011/ayr_yowie_map/ayr_yowie_map_round013_candidates.csv`
- `data/interim/gap_probe_1926_2011/ayr_state_indexes/ayr_state_indexes_round014_candidates.csv`
- `data/interim/gap_probe_1926_2011/hauntedplaces/hauntedplaces_australia_round015_candidates.csv`
- `data/interim/gap_probe_1926_2011/public_books_metadata/public_books_metadata_round017_openlibrary_strict_candidates.csv`
- `data/interim/gap_probe_1926_2011/wikidata_entities/wikidata_entities_round023_strictest_candidates.csv`
- `data/interim/gap_probe_1926_2011/ayr_public_site/ayr_public_site_round024a_candidates.csv`
- `data/interim/gap_probe_1926_2011/public_web_leads/public_web_leads_round025_stricter_candidates.csv`

Generated reports:

- `data/processed/v2/1926_2011_ayr_yowie_map_round013.md`
- `data/processed/v2/1926_2011_ayr_state_indexes_round014.md`
- `data/processed/v2/1926_2011_hauntedplaces_australia_round015.md`
- `data/processed/v2/1926_2011_public_books_metadata_round017_openlibrary_strict.md`
- `data/processed/v2/1926_2011_public_books_metadata_round018_ia_probe.md`
- `data/processed/v2/1926_2011_public_books_metadata_round020_openlibrary_pages3_4.md`
- `data/processed/v2/1926_2011_public_books_metadata_round021_openlibrary_pages3_4_all.md`
- `data/processed/v2/1926_2011_wikidata_entities_round023_strictest.md`
- `data/processed/v2/1926_2011_ayr_public_site_round024a.md`
- `data/processed/v2/1926_2011_public_web_leads_round025_stricter.md`
- `data/processed/v2/1926_2011_gap_public_web_overlay_round023_combined.md`

New scripts:

- `scripts/crawl_ayr_yowie_map.py`
- `scripts/crawl_ayr_state_indexes.py`
- `scripts/crawl_hauntedplaces_australia.py`
- `scripts/crawl_public_books_metadata.py`
- `scripts/crawl_wikipedia_haunted_locations.py`
- `scripts/crawl_wikidata_gap_entities.py`
- `scripts/crawl_ayr_public_site_from_commoncrawl.py`
- `scripts/convert_public_web_leads_to_gap_candidates.py`

## Source-Specific Findings

### AYR / YowieHunters

The public AYR map is the best mapped source found so far:

- Source page: `https://yowiemap.sennaswdev.com/yowiemap.php`
- Parsed public Leaflet markers: `1024`
- Accepted post-1926 candidates after sensitivity downgrade: `825`
- Accepted 1926-2011 candidates: `609`
- Net-new after dedupe: `351`

The AYR state indexes are useful but mostly duplicate the map/base:

- Fetched only seven public state index pages.
- Parsed links: `626`
- Accepted post-1926 candidates: `613`
- Accepted with coordinates: `571`
- Net-new after combined dedupe: `21`

Indigenous-related title handling:

- Titles with `Aboriginal`, `Indigenous`, `First Nations`, `Dreaming`, or `Dreamtime` are downgraded to `lead_only`.
- These require manual cultural sensitivity review before any production use.

### HauntedPlaces.org

The Australia directory exposes public Leaflet markers:

- Source page: `https://www.hauntedplaces.org/Australia`
- Parsed markers: `78`
- Accepted mapped candidates: `78`
- These are undated directory entries, so they help map coverage but not annual trend repair.

### Open Library

Open Library is a stable no-key public metadata lane, but low yield:

- Round017 strict crawl: `68` requests, `232` rows, `33` accepted.
- Accepted rows are mostly public books/story collection metadata.
- Accepted year buckets: `1946-1969: 2`, `1970-1990: 4`, `1991-2011: 27`.
- Mapped yield: `1` reused place coordinate (`Gaol ghosts` / Adelaide Gaol).
- Deeper page probe round020 returned `0` rows because all six page 3-4 requests hit runtime fetch errors.
- Full page 3-4 retry round021 returned `67` ok requests and `0` items, so page 1-2 appears to exhaust useful Open Library results for these query families.

This route is useful for supplementing public-text year coverage but cannot carry the +4000 target.

### Wikidata

Wikidata is a clean no-key public metadata source but very low yield:

- Round022 broad crawl produced too many same-name place false positives (`Yowie Bay`, `Bunyip Post Office`, etc.).
- Round023 strictest keeps only explicit creature/folklore/ghost-story context.
- Final accepted: `5`; mapped: `0`.
- These are undated entity records and should not feed annual trend.

### AYR Public Site via Common Crawl Discovery

Common Crawl URL discovery found public `yowiehunters.com.au` page URLs and the crawler fetched current pages after robots checks:

- Round024a fetched `106` current public pages.
- Accepted: `0`.
- Reason: all fetched pages were duplicate against the current overlay/base.
- Interpretation: AYR public site pages are already represented through AYR map/state index ingestion; this source family should not be expanded further unless new URL ranges are found.

### Prior Public-Web Leads

Older public-web crawl leads were reprocessed with stricter rules:

- Round025 strict initially accepted `2`, but manual inspection showed navigation contamination on non-ghost Adelaide Gaol pages.
- Round025 stricter requires ghost/haunt/paranormal/spirit in title or URL, not only body/navigation.
- Final accepted: `0`.

### Trove / NLA

Trove remains the most important source for reaching +4000 net-new:

- Trove v3 API probe returned `No API key found in request`.
- Trove public search HTML is a JavaScript shell, not parseable result HTML.
- Trove robots disallows `/api/search/*`, so the web app API should not be scraped.

Next high-volume Trove work requires a legitimate Trove API key.

### Blocked Or Low-Yield Routes

- Google Books public API returned HTTP `429` with no-key daily quota effectively unavailable; this needs a real Google Books API key before use.
- Internet Archive advancedsearch remained unstable: the full route hung, and the narrowed round018 IA probe produced `0` rows with `3` runtime fetch errors.
- Simplified Internet Archive probes for `yowie`, `bunyip`, and `Fisher's Ghost` also timed out at 20 seconds each.
- Wikipedia API and direct HTML fetch for the reportedly haunted locations page timed out from the shell environment; no Wikipedia candidates were added.
- Internet Archive metadata route timed out in prior live probes.
- NLA catalogue host connection failed in prior probes.
- GDELT returned rate-limit responses in prior probes.
- AYR forum is behind a Cloudflare managed challenge and presented `noindex,nofollow`; it should not be crawled or bypassed.
- Broad institutional sitemaps were noisy because ghost-tour nav text polluted unrelated pages.
- Common Crawl public index probing was blocked by the current environment usage limit, so it was not pursued.

## Interpretation

The current real crawl proves the 1926-2011 flat trend is partly a source strategy problem:

- Public mapped Yowie report sources add many post-1970 records quickly.
- The 1926-1969 period remains underfilled even after AYR map extraction.
- Haunted-place directory sources add mapped public display locations but often lack event/publication year.
- API-backed newspaper metadata is likely required for large net-new counts in 1926-1969.

## Next Implementation Steps

The next narrowed phase is documented in
`docs/1926-1976-gap-next-phase-plan.md`.

Interim target for that phase:

- Start from the current localhost overlay: `4,427` public records / `1,668`
  mapped records.
- Add about `500` public records, prioritising dated `1926-1976` records.
- Raise mapped records to at least `2,000`, which requires at least `+332`
  mapped records from the current overlay.
- Treat the implied `66.4%` mapped yield requirement as a hard source-selection
  constraint: metadata-only routes can help discovery, but the next accepted
  batch must be map-heavy enough to move the public display layer.

Implementation order:

1. Build a 1926-1976 crawl manifest focused on state libraries, archives, local
   history pages, public institutional pages, and exact public-place routes.
2. Use a Trove API key or manual export only when available; do not scrape
   protected Trove article endpoints.
3. Keep Common Crawl and broad source discovery as optional seed discovery, not
   as a direct accepted-record route.
4. Keep all future sources stage-only until dedupe, date parsing, publicness,
   map eligibility, and sensitivity review pass.
5. Do not count simulation rows from `public/data/frontend-data.experimental-4000.json`; those are `simulated_not_ingested`.

## Operations Requiring Authorization

- Trove API crawl: requires a valid Trove API key and rate-limit agreement.
- Any large external crawl or Common Crawl index query: requires network usage availability.
- Promotion into production `frontend-data.json`: requires explicit user authorization.
- Database import/promote scripts: requires explicit user authorization.
- Git staging, commit, or push: requires explicit user authorization.

## Localhost Source-Family Integration Check

The current localhost overlay remains `public/data/frontend-data.gap-public-web.json`:

- Localhost totals: `4,427` public records / `1,668` mapped records.
- The new `public_web_yowie_report_map`, `public_web_yowie_state_report_index`, and `public_web_haunted_places_directory` rows are now displayed as `Modern public web`, not `Other public source`.
- The new `live_crawl_openalex`, `live_crawl_crossref`, `public_books_metadata_openlibrary`, and `public_wikidata_entity_metadata` rows are displayed as `Academic / catalogue metadata`.
- Record-bearing source-family rollup now reads:
  - `Repository / archive`: `1,609`
  - `Modern public web`: `1,468`
  - `Public-domain text`: `941`
  - `Public institution`: `215`
  - `Academic / catalogue metadata`: `193`
  - `Community-controlled public source`: `1`
- Mapped source-family rollup now reads:
  - `Modern public web`: `1,353`
  - `Public institution`: `172`
  - `Repository / archive`: `73`
  - `Public-domain text`: `68`
  - `Academic / catalogue metadata`: `1`
  - `Community-controlled public source`: `1`

Frontend sync changes:

- `/map`, `/density`, `/source`, `/about`, and the mobile `/` route now use the same `FRONTEND_DATA_URL` data path under localhost.
- The mobile archive route no longer relies on the stale static `mobile-archive.json` snapshot for visible counts.
- The map source legend was moved upward and tightened so the source-family card does not crowd the bottom controls.

Verification:

- `npm run typecheck`
- Playwright localhost checks for `/`, `/map`, `/source`, `/about`, and `/density`

## 1926-1976 Crawl Round 001

Detailed report:

- `docs/1926-1976-gap-crawl-round001-report.md`

Outcome:

- New localhost overlay: `public/data/frontend-data.1926-1976-gap.json`
- Totals: `4,433` public records / `1,674` mapped records.
- Net change from prior overlay: `+6` public records / `+6` mapped records.
- Source of accepted growth: Internet Archive public metadata for Fisher's
  Ghost / Campbelltown rows, all dated `1960`.
- The run stopped after three post-growth strict no-growth routes:
  IA Fisher's Ghost deepening, IA Australian ghost stories, and strict
  OpenAlex/Crossref metadata.

Important access findings:

- SLSA, SLV, and NLA catalogue searches exposed or are likely to expose useful
  1926-1976 rows, but their search endpoints are robots-disallowed for
  automated crawling. They are manual export/review routes only.
- Trove remains the most important next route, but still requires an API key or
  researcher-supplied manual export.
- Open Library was transport-blocked from this environment during the round.
