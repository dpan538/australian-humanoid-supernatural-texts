# Source Route Failure Log

Generated: 2026-06-22

This log records collection routes that have already been tested and should not
be retried without a materially different access method, query strategy, or
human-supplied source list.

## Blocked Or Low-Yield Routes

| Route | Status | Evidence | Next Action |
| --- | --- | --- | --- |
| Trove article pages | blocked | Public article pages and NLA persistent pages return bot-check or script-gated HTML in automated requests. | Use `TROVE_API_KEY`, manual article export, or researcher-supplied article IDs and text. |
| Trove OCR rendition URLs | blocked | `https://trove.nla.gov.au/newspaper/rendition/nla.news-article70993856.txt` and `.3.txt` returned bot-check HTML. | Do not retry without API key or documented public endpoint change. |
| NLA `.txt` article URL | unavailable | `https://nla.gov.au/nla.news-article70993856.txt` returned 404. | Do not retry as a collection route. |
| Trove API unauthenticated | blocked | `https://api.trove.nla.gov.au/v3/result?...` returned `No API key found in request`. | Require environment variable `TROVE_API_KEY`; never commit credentials. |
| OpenAlex metadata pass | exhausted for current query set | 2026-06-22 dry run returned 0 card-ready records; results were duplicates, noise, or metadata-only. | Use only for discovery/citation enrichment, not bulk accepted records. |
| Crossref metadata pass | exhausted for current query set | 2026-06-22 dry run returned 0 card-ready records; mostly duplicate or missing Australia/person-form context. | Use only for scholarly context. |
| Internet Archive broad ghost/Victorian queries | low yield/noisy | Broad searches returned non-Australian Victorian literature, inaccessible OCR, duplicates, or generic metadata. | Use only exact Australian titles or known identifiers. |
| QVMAG broad sitemap crawl | noisy | Produced large `institutional_web` lead-only set; many pages triggered weak words such as art/spirit/power without supernatural person-form evidence. | Do not promote without manual page-level review. |
| AYR expansion and weak-state retries | exhausted | Recent dry runs returned duplicates only. | Avoid further AYR expansion unless new URLs are discovered independently. |

## Current Viable Routes

- Seeded public web rows with inspected public evidence, distinct external IDs,
  and neutral editorial summaries.
- Manual CSV imports from researcher-verified newspaper/library/archive exports.
- Trove API collection only after `TROVE_API_KEY` is supplied through the
  environment.
- Institutional/local-history pages where the public text or public metadata
  clearly supports a person-form narrative, location role, source label, and
  rights/publicness note.

## Frontend Count Note

The map page distinguishes:

- `record_count`: all display records used by Dashboard and Density.
- `strict_map_record_count`: records with at least one strict map location.
- `map_point_count`: strict location points; this can exceed strict record count
  when one record has multiple verified locations.

The map should display strict records as the headline count and expose point
count as a secondary health metric.
