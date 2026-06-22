# Collection Route Registry

- Generated: `2026-06-22T06:10:08+00:00`
- Schema version: `collection-routes/v1`
- Routes: `64`

## Status Counts
- `blocked_auth`: 1
- `discovery_only`: 1
- `exhausted`: 1
- `low_yield`: 11
- `manual_only`: 1
- `productive`: 49

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
| sprint_wikisource_southeast_exact_texts | low_yield | Wikisource | exact_chapter_html_text | 66 | 63 | 10 | 3 |  | Keep as probe/discovery route only |
| sprint_internet_archive_roth_queensland_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 15 | 15 | 2 | 0 |  | Scale productive route |
| sprint_pga_australian_fairy_tales_exact_texts | productive | Project Gutenberg Australia | exact_title_html_text | 36 | 36 | 3 | 0 |  | Scale productive route |
| sprint_map_queue_geocode_verification | low_yield | OpenStreetMap Nominatim | exact_queue_gazetteer_verification | 87 | 87 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_victorian_collections_story_probe | low_yield | Victorian Collections | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_sa_history_network_directory_probe | low_yield | History Trust of South Australia | directory_seed_probe | 3 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_territory_stories_public_probe | low_yield | Library & Archives NT | public_repository_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_wikisource_euahlayi_exact_texts | productive | Wikisource | exact_chapter_html_text | 62 | 62 | 12 | 0 |  | Scale productive route |
| sprint_project_gutenberg_westbury_australian_fairy_tales | productive | Project Gutenberg | exact_plain_text | 32 | 32 | 0 | 0 |  | Scale productive route |
| sprint_project_gutenberg_robertson_australian_tales | productive | Project Gutenberg | exact_plain_text | 22 | 22 | 4 | 0 |  | Scale productive route |
| sprint_project_gutenberg_barry_bunyip_stories | productive | Project Gutenberg | exact_plain_text | 20 | 20 | 2 | 0 |  | Scale productive route |
| sprint_internet_archive_kamilaroi_kurnai_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 28 | 28 | 6 | 0 |  | Scale productive route |
| sprint_internet_archive_sa_folklore_manners_customs_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 16 | 16 | 2 | 0 |  | Scale productive route |
| sprint_internet_archive_native_tribes_south_australia_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 21 | 21 | 1 | 0 |  | Scale productive route |
| sprint_internet_archive_eaglehawk_crow_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 26 | 22 | 7 | 1 |  | Scale productive route |
| sprint_internet_archive_moore_wa_diary_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 19 | 18 | 2 | 0 |  | Scale productive route |
| sprint_internet_archive_dawson_victoria_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 25 | 25 | 9 | 0 |  | Scale productive route |
| sprint_internet_archive_smyth_victoria_vol1_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 32 | 29 | 0 | 3 |  | Scale productive route |
| sprint_internet_archive_smyth_victoria_vol2_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 30 | 30 | 4 | 0 |  | Scale productive route |
| sprint_internet_archive_roth_tasmania_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 25 | 25 | 5 | 0 |  | Scale productive route |
| sprint_internet_archive_beveridge_victoria_riverina_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 11 | 11 | 2 | 0 |  | Scale productive route |
| sprint_internet_archive_fraser_nsw_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 27 | 27 | 2 | 0 |  | Scale productive route |
| sprint_internet_archive_lumholtz_queensland_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 23 | 23 | 0 | 0 |  | Scale productive route |
| sprint_internet_archive_lang_queensland_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 27 | 27 | 6 | 0 |  | Scale productive route |
| sprint_internet_archive_northern_tribes_central_australia_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 29 | 29 | 9 | 0 |  | Scale productive route |
| sprint_internet_archive_curr_australian_race_vol2_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 24 | 24 | 3 | 0 |  | Scale productive route |
| sprint_internet_archive_curr_australian_race_vol3_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 27 | 27 | 3 | 0 |  | Scale productive route |
| sprint_internet_archive_peck_australian_legends_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 21 | 19 | 6 | 2 |  | Scale productive route |
| sprint_pga_favenc_austral_tropics_exact_text | productive | Project Gutenberg Australia | exact_plain_text | 21 | 18 | 2 | 2 |  | Scale productive route |
| sprint_pga_clarke_old_tales_young_country_exact_text | productive | Project Gutenberg Australia | exact_plain_text | 18 | 12 | 1 | 5 |  | Scale productive route |
| sprint_internet_archive_curr_australian_race_vol1_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 23 | 21 | 0 | 1 |  | Scale productive route |
| sprint_internet_archive_suttor_fishers_ghost_exact_section | low_yield | Internet Archive | exact_item_metadata_djvu_text_section_slice | 1 | 1 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_internet_archive_suttor_australian_stories_retold_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 16 | 12 | 10 | 1 |  | Scale productive route |
| sprint_internet_archive_swan_tales_australian_life_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 13 | 12 | 1 | 0 |  | Scale productive route |
| sprint_internet_archive_ridley_kamilaroi_languages_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 24 | 23 | 7 | 1 |  | Scale productive route |
| sprint_internet_archive_hill_thornton_notes_nsw_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 8 | 8 | 31 | 0 |  | Scale productive route |
| sprint_internet_archive_nicolay_notes_wa_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 8 | 8 | 3 | 0 |  | Scale productive route |
| sprint_internet_archive_moore_wa_vocabulary_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 17 | 17 | 13 | 0 |  | Scale productive route |
| sprint_internet_archive_roth_garson_tasmania_1890_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 25 | 24 | 13 | 0 |  | Scale productive route |
| sprint_internet_archive_roth_nq_burial_ceremonies_exact_article | productive | Internet Archive | exact_item_metadata_and_djvu_text | 15 | 14 | 9 | 1 |  | Scale productive route |
| sprint_internet_archive_miles_demigods_daemonia_exact_article | productive | Internet Archive | exact_item_metadata_and_djvu_text | 19 | 18 | 7 | 0 |  | Scale productive route |
| sprint_internet_archive_lawson_joe_wilson_ghost_stories_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 28 | 27 | 14 | 0 |  | Scale productive route |
| sprint_project_gutenberg_lawson_on_the_track_exact_text | productive | Project Gutenberg | exact_plain_text | 11 | 11 | 4 | 0 |  | Scale productive route |
| sprint_project_gutenberg_lawson_children_of_the_bush_exact_text | productive | Project Gutenberg | exact_plain_text | 20 | 17 | 6 | 1 |  | Scale productive route |
| sprint_sacred_texts_nw_wa_customs_traditions_exact_text | productive | Internet Sacred Text Archive | exact_full_text_html | 12 | 12 | 6 | 0 |  | Scale productive route |
| sprint_internet_archive_boothby_crime_under_seas_phantom_stockman_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 22 | 22 | 8 | 0 |  | Scale productive route |
| sprint_internet_archive_nisbet_colonial_tramp_beliefs_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 12 | 11 | 5 | 1 |  | Scale productive route |
| sprint_internet_archive_eden_fifth_continent_beliefs_exact_text | low_yield | Internet Archive | exact_item_metadata_and_djvu_text | 5 | 5 | 2 | 0 |  | Keep as probe/discovery route only |
| sprint_pga_cambridge_at_midnight_haunted_house_exact_text | productive | Project Gutenberg Australia | exact_plain_text | 27 | 21 | 9 | 3 |  | Scale productive route |
| sprint_pga_clarke_human_repetends_exact_text | low_yield | Project Gutenberg Australia | exact_plain_text | 4 | 3 | 1 | 1 |  | Keep as probe/discovery route only |
| sprint_pga_clarke_australian_tales_exact_text | productive | Project Gutenberg Australia | exact_plain_text | 19 | 18 | 1 | 0 |  | Scale productive route |
