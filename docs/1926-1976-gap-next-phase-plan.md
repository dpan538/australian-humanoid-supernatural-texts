# 1926-1976 Gap Next Phase Plan

Generated: 2026-06-30

This document narrows the next AusFigures data-deepening phase to the visible
1926-1976 trough. It updates the working target from the broad 1926-2011 gap
to a smaller, measurable crawl-and-clean cycle:

- current localhost overlay: `4,427` public records / `1,668` mapped records
- next phase target: about `+500` public records
- mapped target: at least `2,000` mapped records
- required mapped growth from current overlay: at least `+332`
- implied mapped yield on the next `+500`: at least `66.4%`

All new rows remain stage-only until source review, dedupe, date parsing,
publicness checks, sensitivity review, and explicit promotion are complete.

## Boundary

AusFigures remains a source-grounded public-text research archive. A public
source does not verify a supernatural claim, and a map marker is a public
display location for a record, not habitat, population, or proof.

This phase must not change ontology, classification semantics, map eligibility
logic, or source-family semantics. It must not bypass robots, paywalls, private
access, access-control screens, or restricted cultural material.

## Current Evidence

The current overlay already moved the whole archive to `4,427 / 1,668`, but the
new growth is concentrated after 1970. The early-middle trough is still real in
the current staged data.

| period | current records | current mapped | latest overlay added records | latest overlay added mapped | evidence |
|---|---:|---:|---:|---:|---|
| 1926-1939 | 32 | 23 | 9 | 9 | Mostly existing `modern_web`, `repository_full_text`, and AYR map additions. |
| 1940-1959 | 10 | 6 | low single digits | low single digits | Sparse across all current source families; no scalable route yet. |
| 1960-1976 | 86 | 51 | partial from 1970-1990 bucket | partial from 1970-1990 bucket | Growth begins through modern web, AYR map, and metadata lanes, but remains thin before 1970. |
| 1926-1976 total | 128 | 80 | about 16 before 1970, plus some 1970-1976 rows | about 14 before 1970, plus some 1970-1976 rows | Current data confirms this is still the priority trough. |
| 1977-2011 | 1,001 | 772 | 166 in 1991-2011 plus much of 1970-1990 | 132 in 1991-2011 plus much of 1970-1990 | AYR and modern public web routes are much stronger here. |

The previous net-new crawl round added `530` records and `462` map flags, but
only `9 / 9` landed in 1926-1945 and `7 / 5` landed in 1946-1969. That means
the next phase cannot rely on the same source mix.

## Source-Family Diagnosis

| route family | status for 1926-1976 | decision |
|---|---|---|
| AYR public Yowie map and state indexes | Strong mapped yield after 1970; weak before 1970; now duplicate-heavy. | Use only for targeted verification and missed early rows, not broad reruns. |
| HauntedPlaces directory | High mapped yield, but mostly undated. | Useful for map growth only when a dated public source can be attached. |
| ABC/public media pages | High precision, limited volume, skewed modern. | Continue exact-place pages and older archive pages, but avoid broad noisy scans. |
| Open Library/Wikidata/OpenAlex/Crossref | Clean public metadata, low mapped yield. | Use as discovery/source-chain support, not mapped-count engine. |
| Internet Archive broad search | Prior no-key probes timed out or yielded zero strict-geo rows. | Avoid broad reruns; use exact item/title routes only. |
| State library, archive, local history, institutional pages | Underused for this period and more likely to include dated place evidence. | Make this the primary no-key crawl lane. |
| Trove/NLA newspapers and gazettes | Best-fit source for 1926-1976 dated public records, but API key is not available yet. | Keep as highest priority once key/manual export exists; do not scrape protected endpoints. |

## Acceptance Targets

The phase target is not merely `+500` rows; it is `+500` rows that repair the
trough and can survive review.

| bucket | target added records | target added mapped | notes |
|---|---:|---:|---|
| 1926-1939 | 120 | 75 | Newspaper/gazette/manual source chains are likely required. |
| 1940-1959 | 160 | 105 | Highest priority because the current count is only `10 / 6`. |
| 1960-1976 | 170 | 120 | Combine early AYR/report language with institutional and library sources. |
| dated spillover 1977-1985 | 50 | 32 | Allowed only when the same source run produces strong nearby records. |
| total | 500 | 332 | Reaches about `4,927` public records and at least `2,000` mapped. |

At least `450` of the `500` new rows should be dated `1926-1976`. Undated
mapped rows can help the map, but they do not repair the annual trend and
should not dominate this phase.

## Proposed Query Families

Use period language and place constraints rather than broad monster terms.

| family | example terms | intended source lane |
|---|---|---|
| Yowie/Yahoo report language | `yowie`, `yahoo`, `hairy man`, `wild man`, `ape man`, `gorilla man`, `bush ape`, `devil-devil`, `debil-debil` with `sighting`, `tracks`, `footprints`, `encounter`, `mystery creature` | Trove/API later, state libraries, local newspapers, local history pages. |
| Newspaper headline variants | `strange creature`, `mysterious man`, `wild man of`, `hairy man of`, `bush mystery`, `monster scare`, `tracks found` plus state/place names | 1926-1959 newspapers, gazettes, clipping pages. |
| Ghost/apparition public places | `ghost`, `haunted`, `apparition`, `phantom`, `spectre`, `white lady`, `resident ghost`, `ghost story` plus prisons, theatres, hotels, bridges, asylums, stations | Institutional history pages, state libraries, councils, local history societies. |
| Named public places | `Port Arthur`, `Princess Theatre`, `Adelaide Gaol`, `Picton`, `Quarantine Station`, `Monte Cristo`, `Old Melbourne Gaol`, `Boggo Road`, `Fisher's Ghost` with older date filters | Map-first institutional and catalogue searches. |
| Local legend/source voice | `local legend`, `district story`, `old residents`, `bush legend`, `folklore`, `legend of` plus locality | Local history pages and public-domain books. |
| Public Indigenous-related labels | Public source-voice terms only, such as `Quinkan`, `Nargun`, `Mimih`, `Mokoi`, `Mamu`, `Pangkarlangu`, `Wandjina/Wanjina` | Discovery and review only; no automatic production promotion. |

## Proposed Source Targets

Priority no-key targets for the next crawl cycle:

| target | reason | crawl stance |
|---|---|---|
| State Library Victoria public pages and catalogue snippets | Strong public-place ghost and theatre/prison history material. | Section-specific, low-rate pages; no broad sitemap scans. |
| State Library NSW public pages and catalogue/public collection pages | Good fit for Fisher's Ghost, Picton, Blue Mountains, local newspaper references. | Place-first query pages and stable public item pages. |
| State Library Queensland / John Oxley Library public pages | Likely source for `yowie`, `hairy man`, `bunyip`, `Boggo Road`, regional folklore. | Query-family probes with strict Australia/place filters. |
| State Library South Australia / State Records SA public pages | Adelaide Gaol, theatres, local history, digitised public records. | Exact place pages and catalogue metadata. |
| State Library WA / Battye Library public pages | WA regional Yowie/wild man/local legend routes. | Place-first and title-first probes. |
| Libraries Tasmania / eHeritage | Port Arthur, Hobart, Richmond Bridge, local apparitions. | Exact place and public collection pages. |
| Local council and local history society pages | Often dated, place-specific, public, and map-eligible. | Small seed lists, two-second minimum delay per host. |
| Public-domain book exact-title routes | Useful for source-chain and date context, low mapped yield. | Exact title only; no broad global searches. |
| Trove/NLA newspapers and gazettes | Best eventual source for 1926-1976. | Use official API or manual export only; wait for key/export. |

## Crawl And Clean Plan

1. Build a `1926_1976` seed manifest with source target, query family, date
   window, source host, expected publicness, and risk flags.
2. Run no-key probes in small batches: 25 to 50 source/query combinations per
   round, maximum 5 sample records per query before cleaning.
3. Use host-aware rate limits: at least 1 second per request globally, at least
   2 seconds for small local-history or council sites, and stop on errors.
4. Store all probe evidence in `data/interim/gap_probe_1926_1976/` with raw
   request summaries separate from candidate CSVs.
5. Promote only to candidate rows when the page/metadata has a stable public
   URL, visible date or publication year, Australian relationship, source
   voice, and a non-inferred place or public display location.
6. Dedupe after every round against the current overlay and within the new
   candidate set by URL, title, year, source, place, and figure label.
7. Import into a localhost overlay only after the candidate set passes source
   family mapping, date-bucket counts, publicness checks, and map invariant
   checks.
8. Production import happens only after the phase target is met and the
   candidate review report is approved.

## Quality Gates

A row can count toward the `+500` phase only if it has:

- public source URL or public metadata URL;
- year or date range inside the accepted target window;
- source name and source type;
- query family and query string provenance;
- title and short source-grounded evidence summary;
- narrative/source label in source voice;
- duplicate status;
- publicness/access status;
- cultural sensitivity risk flags where relevant.

A row can count toward the `+332` mapped growth only if it also has:

- an Australian public display location or locality;
- map confidence and geocode source;
- location role separated from claim truth;
- no inferred habitat/population/proof wording;
- `mapped_record_count == map_flags.length` after overlay build.

## Stop Rules

Stop or downgrade a route when:

- it produces mostly duplicates for two consecutive rounds;
- it returns navigation-contaminated pages rather than source-specific content;
- it lacks dates for most rows;
- it lacks map-eligible public locations;
- robots, rate limits, or access controls signal that the source should not be
  crawled;
- Indigenous-related material is not clearly public, source-voiced, and safe
  for archive display.

## Minimal Next Implementation Steps

1. Add a `1926-1976` crawl manifest CSV or JSON under
   `data/interim/gap_probe_1926_1976/`.
2. Add a small probe script that reads the manifest, performs robots-aware
   public page requests, and writes request summaries plus stage-only samples.
3. Add a cleaner that emits candidate rows with `query_family`, `date_window`,
   `source_target`, `publicness_status`, `rights_access_status`, and
   `risk_flags`.
4. Add an overlay builder that merges only reviewed candidate rows into a new
   localhost file, for example
   `public/data/frontend-data.1926-1976-gap.json`.
5. Verify localhost on `/`, `/density`, `/map`, `/source`, and `/about` with
   the overlay data URL.
6. Produce a phase report showing accepted rows, rejected rows, duplicates,
   year buckets, source families, query families, mapped count, and remaining
   gap.

## Operations Requiring Authorization

- Long-running or high-volume external crawls.
- Trove API crawling or any API-key based source route.
- Any production import into `public/data/frontend-data.json` or SQLite.
- Any change to ontology, classification semantics, or map eligibility logic.
- Any git staging, commit, or push.
