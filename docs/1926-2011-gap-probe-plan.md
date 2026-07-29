# 1926-2011 Gap Probe Plan

This document defines the next AusFigures data-deepening step after the initial
gap audit. The goal is to find enough post-1926 public-source evidence to
understand the annual trend, then simulate how reviewed records could fill the
system. It is not a production import plan.

## Boundary

AusFigures is a source-grounded public-text research archive. A public source
existing does not verify a supernatural claim, and a map location is a display
location for a record, not proof of habitat, population, or event truth.

This phase will not change ontology, classification semantics, map eligibility,
frontend data, metadata, SEO, or production deployment. It will not bypass
robots, paywalls, private access, or restricted cultural material.

## Current Finding

The annual density line is calculated from public records by `record.year`, with
mapped records layered separately. The `1930-1969` band currently has only a
small number of public records before map filtering, so the trough is not a map
eligibility issue.

The current public records also lack linked `query_id` provenance. That means
the next phase must record query family, query string, source target, date
window, hit count, and sample rank at the probe/candidate layer. Without that,
future audits cannot distinguish real source scarcity from query-design gaps.

## What "Simulated Fill" Means

The simulation is an aggregate planning model. It creates CSV rows such as:

- year
- current public records
- target public records
- simulated additional records
- simulated source family
- estimated mapped share
- `simulated_not_ingested`

These rows are not records. They are not candidates. They are not imported into
SQLite and are not exported to `public/data/frontend-data.json`. They exist to
show how annual trend coverage would look if future reviewed source items filled
the sparse years.

## Query Families

The agreed exploratory families are:

- Yowie and Yahoo named forms: `Yowie`, `Yahoo-devil`, `Yahoo devil devil`,
  `devil-devil`, and `debil-debil` variants.
- Hairy humanoid descriptors: `hairy man`, `hairyman`, `wild man`, `wildman`,
  `ape man`, `Australian ape`, `Australian gorilla`, and `bush ape`.
- Report and headline language: `tracks`, `footprints`, `sighting`,
  `encounter`, `monster`, `creature`, `scare`, `mystery man`, and
  `mystery creature`, with Australian place constraints.
- Ghost and apparition public-place records: `ghost`, `apparition`, `phantom`,
  `spectre`, `spook`, `haunted`, `white lady`, `resident ghost`, and
  `ghost story`, prioritising public institutional or archive-backed pages.
- Local legend/source-voice forms: `local legend`, `bush legend`,
  `old residents`, and `district story`, preserving source wording.
- Public named figure records requiring sensitivity review: `Wandjina`,
  `Wanjina`, `Quinkan`, `Quinkin`, `Nargun`, `Mimih`, `Mokoi`,
  `Pangkarlangu`, `Mamu`, `Yaroma`, and `Yara-ma-yha-who`.

## Source Targets

Priority source targets:

- Trove newspapers and gazettes metadata through official API or manual export.
- Trove magazines and newsletters metadata through official API or manual export.
- National Library of Australia catalogue metadata.
- State library/archive public pages and finding aids.
- Local history public pages with source citations.
- Public-domain or publicly indexed Australian books.
- Museum, heritage, institutional media, and broadcast archive pages.

Tourism pages remain discovery-only unless they point to a stronger public
source. Catalogue metadata remains a lead until item-level publicness and source
evidence are reviewed.

## Safe Probe Rules

- Use public metadata and public pages only.
- Use `TROVE_API_KEY` for automated Trove metadata counts; do not probe
  unauthenticated article text endpoints.
- Rate limit first probes to at least 1 second per request, or 2 seconds for
  smaller local-history sites.
- Cap first probes by source target and query family.
- Store hit counts and a small number of samples; do not bulk ingest.
- Preserve `query_family`, `query_string`, `date_window`, `source_target`,
  `hit_count`, `sample_rank`, `publicness_status`, `rights_access_status`, and
  `risk_flags`.
- Treat Indigenous-related rows as public-source representations only and keep
  cultural sensitivity review mandatory.

## Local Artifacts

The local no-network step is:

```bash
python3 scripts/audit_1926_2011_gap.py
```

It writes:

- `data/processed/v2/1926_2011_gap_audit.md`
- `data/interim/gap_probe_1926_2011/year_bucket_evidence.csv`
- `data/interim/gap_probe_1926_2011/annual_gap_evidence.csv`
- `data/interim/gap_probe_1926_2011/planned_probe_queries.csv`
- `data/interim/gap_probe_1926_2011/simulated_gap_fill_projection.csv`

The Trove request planner is also safe by default:

```bash
python3 scripts/probe_trove_gap_counts.py
```

That writes a dry-run request plan only. A live Trove metadata-count probe must
be explicit:

```bash
TROVE_API_KEY=... python3 scripts/probe_trove_gap_counts.py --live --max-requests 80
```

Live probe rows remain `metadata_only` / `not_ingested`; they are evidence for
review and planning, not archive records.

## 4000-Record Localhost Overlay

The current working target is an experimental projection of 4,000 additional
post-1926 rows, with the localhost mapped total raised to at least 2,500. This
is a visual/data-load simulation only. It is useful for checking whether the
annual trend, density panels, source composition, and map can represent the
intended scale after future reviewed crawling.

Generate the overlay with:

```bash
python3 scripts/build_experimental_gap_overlay.py --include-simulated-map-flags
```

That writes:

- `data/interim/gap_probe_1926_2011/frontend-data.experimental-4000.json`
- `public/data/frontend-data.experimental-4000.json`
- `data/processed/v2/1926_2011_gap_localhost_overlay.md`

The overlay rows are marked with:

- `ingestion_status: simulated_not_ingested`
- `publicness_code: experimental_projection`
- `relevance_code: needs_review_projection`
- `map_confidence: simulation_only`

They do not overwrite `public/data/frontend-data.json`, do not enter SQLite,
and must not be treated as reviewed records. Run localhost against the
experimental file with:

```bash
NEXT_PUBLIC_FRONTEND_DATA_URL=/data/frontend-data.experimental-4000.json npm run dev
```

Without that environment variable, the app still reads the production frontend
data file.

## Live Crawl Round 001

Round 001 ran a real public-metadata crawl rather than a projection. It used
OpenAlex and Crossref public APIs for the 1926-2011 window, with short request
timeouts, per-request CSV/NDJSON writes, and no production promotion.

Latest artifacts:

- `data/interim/gap_probe_1926_2011/live_crawl/public_metadata_live_candidates.csv`
- `data/interim/gap_probe_1926_2011/live_crawl/public_metadata_live_request_summary.csv`
- `data/interim/gap_probe_1926_2011/live_crawl/public_metadata_live_raw.ndjson`
- `data/processed/v2/1926_2011_live_public_metadata_crawl.md`
- `data/interim/gap_probe_1926_2011/live_crawl/public_metadata_live_round002_candidates.csv`
- `data/interim/gap_probe_1926_2011/live_crawl/public_metadata_live_round002_request_summary.csv`
- `data/interim/gap_probe_1926_2011/live_crawl/public_metadata_live_round002_raw.ndjson`
- `data/processed/v2/1926_2011_live_public_metadata_crawl_round002.md`
- `public/data/frontend-data.live-crawl.json`
- `data/processed/v2/1926_2011_live_candidate_overlay.md`

Round 002 observed yield:

- Requests: 80
- Sampled metadata rows: 2,374
- Clean public metadata candidates before overlay dedupe: 35
- Localhost overlay candidates after dedupe: 31
- Clean rate from sampled metadata: 1.47%
- Source yield: OpenAlex 11 clean candidates, Crossref 24 clean candidates
- Year signal: 1930-1949 = 1, 1950-1969 = 3, 1970-1989 = 7, 1990-2011 = 24

Localhost can be run against the real candidate overlay with:

```bash
NEXT_PUBLIC_FRONTEND_DATA_URL=/data/frontend-data.live-crawl.json npm run dev
```

This live overlay raises public records from 3,809 to 3,840 and leaves mapped
records at 1,206. That is intentional: metadata candidates are not map-eligible
until a reviewed public place/location role exists.

After later crawl rounds, the cleaning rule was tightened. Place-plus-figure
families now require the place term and the figure term together, for example
`Grafton` + `Yowie`, or `Port Arthur` + `ghost/haunted`. This dropped the
combined live overlay from the earlier inflated candidate count to 88 strict
deduped public metadata candidates. The current cumulative status is documented
in `data/processed/v2/1926_2011_live_crawl_cumulative.md`, and localhost now
uses `public/data/frontend-data.live-crawl.json` with 3,897 public records and
1,206 mapped records.

Internet Archive was tested with a small live API request from this environment
and timed out after 15 seconds. It should be retried later with a longer
network window or from a less restricted connection. Trove remains blocked for
live API crawling until `TROVE_API_KEY` is supplied.

## Review Gates Before Any Import

A probe hit can become a candidate only after:

- source page or metadata is public and stable;
- rights/access status is acceptable;
- query and source provenance are recorded;
- duplicate status is checked;
- narrative type and source voice are reviewed;
- publicness and cultural sensitivity are reviewed;
- location role is separated from map eligibility;
- source excerpt is short and source-grounded.

A candidate can become a production record only after a separate promotion step
and explicit approval.
