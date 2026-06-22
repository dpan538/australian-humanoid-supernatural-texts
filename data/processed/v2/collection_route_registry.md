# Collection Route Registry

- Generated: `2026-06-22T04:54:26+00:00`
- Schema version: `collection-routes/v1`
- Routes: `21`

## Status Counts
- `blocked_auth`: 1
- `discovery_only`: 1
- `exhausted`: 1
- `low_yield`: 6
- `manual_only`: 1
- `productive`: 11

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
| internet_sacred_texts_exact_ethnography | productive | Internet Sacred Text Archive | exact_chapter_html_text | 20 | 20 | 0 | 0 |  | Continue only exact chapter-level extraction with named supernatural/person-form entities; avoid broad site searching. |
| wikisource_australian_ethnography_exact_text | productive | Wikisource | exact_chapter_html_text | 10 | 10 | 0 | 0 |  | Continue only exact chapter-level extraction with named supernatural/person-form entities; avoid broad site searching. |
| sprint_ista_central_australia_exact_texts | productive | Internet Sacred Text Archive | exact_chapter_html_text | 44 | 42 | 3 | 2 |  | Scale productive route |
| sprint_ista_northern_australia_exact_texts | productive | Internet Sacred Text Archive | exact_chapter_html_text | 16 | 16 | 5 | 0 |  | Scale productive route |
| sprint_wikisource_southeast_exact_texts | productive | Wikisource | exact_chapter_html_text | 62 | 59 | 10 | 3 |  | Scale productive route |
| sprint_internet_archive_roth_queensland_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 15 | 15 | 2 | 0 |  | Scale productive route |
| sprint_pga_australian_fairy_tales_exact_texts | productive | Project Gutenberg Australia | exact_title_html_text | 22 | 22 | 3 | 0 |  | Scale productive route |
| sprint_map_queue_geocode_verification | productive | OpenStreetMap Nominatim | exact_queue_gazetteer_verification | 50 | 50 | 0 | 0 |  | Scale productive route |
| sprint_victorian_collections_story_probe | low_yield | Victorian Collections | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_sa_history_network_directory_probe | low_yield | History Trust of South Australia | directory_seed_probe | 2 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_territory_stories_public_probe | low_yield | Library & Archives NT | public_repository_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_wikisource_euahlayi_exact_texts | productive | Wikisource | exact_chapter_html_text | 39 | 39 | 8 | 0 |  | Scale productive route |
