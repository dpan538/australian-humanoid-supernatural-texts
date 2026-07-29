# 1926-1976 Gap Crawl Round 001 Report

Generated: 2026-06-30

This round started the next 1926-1976 exploratory crawl phase. It used only
public pages or public metadata endpoints, kept all rows stage-only, and did
not modify production `public/data/frontend-data.json`.

## Baseline And Result

| metric | before round | after round | change |
|---|---:|---:|---:|
| public records | 4,427 | 4,433 | +6 |
| mapped records | 1,668 | 1,674 | +6 |
| map flags | 1,668 | 1,674 | +6 |
| 1930-1969 density bucket | 62 | 68 | +6 |

Current localhost overlay:

- `public/data/frontend-data.1926-1976-gap.json`
- localhost URL: `http://127.0.0.1:3000`
- dev server data env:
  `NEXT_PUBLIC_FRONTEND_DATA_URL=/data/frontend-data.1926-1976-gap.json`

## Accepted Growth

The only accepted growth came from Internet Archive public metadata for
Fisher's Ghost / Campbelltown rows:

| source route | raw/staged rows | strict accepted | mapped | year bucket | note |
|---|---:|---:|---:|---|---|
| Internet Archive, Fisher's Ghost metadata | 493 rows in interrupted broad IA run | 6 | 6 | 1946-1969 | All accepted rows are 1960 IA metadata items with Campbelltown display coordinates reused from the curated known-place anchor. |

The two initially accepted `Naked Bunyip` rows were manually strict-rejected as
title false positives and are not included in the overlay.

## No-Growth / Blocked Routes

| round | route | result | decision |
|---|---|---:|---|
| round026 | ABC public Algolia search, 1926-1976, 60 queries / 120 pages | 0 accepted / 0 mapped | Pause broad ABC reruns for this phase. |
| round027 | Open Library through Python `urlopen` | 102 request failures, SSL EOF | Transport-blocked in current environment. |
| round028 | Open Library through `curl` | connection timeouts; interrupted before output | Pause Open Library until network route improves. |
| round029 | Internet Archive through `curl` | 20 connect failures | Switched IA transport to `urlopen`. |
| round031 | IA Fisher's Ghost exact deepening after overlay | 0 accepted; 6 duplicates | Fisher's Ghost IA exact route exhausted for net-new. |
| round032 | IA Australian ghost stories broad exact family | 0 accepted | Pause broad IA ghost route; high out-of-window/noise. |
| round033 | OpenAlex/Crossref exact metadata | 5 initial clean rows, all strict-rejected | Cleaner updated for Federici name false positives and biological `ghost crab` noise. |

## Robots / Access Findings

These routes are useful leads but were not automated further:

| target | finding | decision |
|---|---|---|
| SLSA catalogue search | Search page exposed promising catalogue rows for Fisher's Ghost and Australian ghost stories, but `robots.txt` disallows `/search`. | Manual export/review only. |
| SLV discovery search | `find.slv.vic.gov.au/robots.txt` disallows `/discovery/search`. | Manual export/review only. |
| NLA catalogue search | `catalogue.nla.gov.au/robots.txt` disallows `/search?*`. | Manual export/review only. |
| Trove API/search | Trove API still requires key, and robots disallow `/api/search/*`. | Wait for API key or manual export. |
| Bing search | `/search` is disallowed by robots. | Not used for automated seed crawling. |
| DuckDuckGo HTML search | Returned HTTP 403. | Not bypassed. |
| SLNSW collection search | Returned HTTP 403. | Not bypassed. |

## Script Changes

- `scripts/crawl_public_books_metadata.py`
  - added `--year-start` and `--year-end`;
  - routed Internet Archive fetches through `urllib` because `curl` failed from
    this environment;
  - left Open Library paused after transport failures.
- `scripts/crawl_gap_public_metadata.py`
  - added `--year-start` and `--year-end`;
  - tightened Crossref/OpenAlex cleaning for `federici_princess_theatre_named`;
  - added biological `ghost crab(s)` noise handling.
- `lib/source-view-data.ts`
  - source register metrics and rows now count record-bearing sources/types
    only, so zero-record fallback rows no longer show `Other public source`.

## Localhost Verification

Rendered checks passed with Playwright after clicking through the entry view:

| route | expected state |
|---|---|
| `/` | `1,674 mapped / 4,433 public records`; no `Other public source` text. |
| `/map` | `1,674 mapped / 4,433 public records`; repository/archive mapped count increased to `79`. |
| `/density` | `4,433 PUBLIC RECORDS / 1,674 MAPPED`; 1930-1969 bucket increased from `62` to `68`. |
| `/source` | `SOURCE ORGS 48`, `SOURCE TYPES 29`, `PUBLIC RECORDS 4,433`; no `Other public source` text. |
| `/about` | `4,433` public records and `1,674` mapped records visible. |

## Stop Condition

This crawl round stopped because the target was not reached but the post-growth
routes produced three consecutive strict no-growth outcomes:

1. IA Fisher's Ghost deepening: 0 net-new.
2. IA Australian ghost stories: 0 net-new.
3. OpenAlex/Crossref strict metadata: 0 net-new after false-positive review.

The main bottleneck is no longer cleaning capacity; it is legitimate source
access for dated 1926-1976 newspaper/catalogue records. The next productive
step is Trove API access or manual exports from SLSA/SLV/NLA/state catalogue
searches that respect those sites' robots policies.
