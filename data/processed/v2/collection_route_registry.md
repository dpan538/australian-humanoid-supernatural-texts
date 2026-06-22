# Collection Route Registry

- Generated: `2026-06-22T03:11:05+00:00`
- Schema version: `collection-routes/v1`
- Routes: `9`

## Status Counts
- `blocked_auth`: 1
- `discovery_only`: 1
- `exhausted`: 1
- `low_yield`: 3
- `manual_only`: 1
- `productive`: 2

## Stop Rule

Collectors must not retry routes marked `exhausted`, `blocked_auth`, `blocked_robots`, `blocked_access_control`, `manual_only`, or `rejected_source` unless the route's explicit retry condition has changed.

## Routes

| route_id | status | organisation | method | seen | accepted | duplicates | rejected | blocker | next_action |
|---|---:|---|---|---:|---:|---:|---:|---|---|
| trove_api_without_key | blocked_auth | National Library of Australia | api | 0 | 0 | 0 | 0 | missing_api_key | Wait for supplied API key or use manually exported article records. |
| trove_nla_article_text_endpoints | manual_only | National Library of Australia | public_html_or_text_probe | 0 | 0 | 0 | 0 | access_control_or_unavailable_text | Do not probe alternative unauthenticated article text URLs. |
| openalex_crossref_current_terms | low_yield | OpenAlex / Crossref | api | 80 | 0 | 0 | 80 | low_relevance_metadata_only | Pause broad scholarly metadata reruns. |
| ayr_broad_crawl | exhausted | Australian Yowie Research | sitemap_or_archive_crawl | 985 | 0 | 900 | 85 | duplicate_dominated | Use only for verification, source-chain enrichment, or specific modern witness pages. |
| generic_institution_sitemap_scans | low_yield | multiple | whole_site_sitemap_scan | 200 | 0 | 0 | 200 | high_navigation_noise | Replace broad scans with section-specific probes. |
| internet_archive_broad_ghost | low_yield | Internet Archive | metadata_and_ocr_api | 100 | 0 | 0 | 100 | high_noise_non_australian | Use only item-level Australian relationship filters and public OCR verification. |
| tourism_ghost_sites | discovery_only | multiple | public_html | 0 | 0 | 0 | 0 | weak_source_tier | Use only for discovery and source-chain tracing. |
| marriner_princess_theatre_history | productive | Marriner Group | seeded_public_page | 1 | 1 | 0 | 0 |  | Use as a model for section-specific, source-verified institutional seeds. |
| project_gutenberg_australia_exact_folklore | productive | Project Gutenberg Australia | exact_title_html_text | 30 | 30 | 0 | 0 |  | Continue exact-title book-level extraction; avoid broad global ghost searches. |
