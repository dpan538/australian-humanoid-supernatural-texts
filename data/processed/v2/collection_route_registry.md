# Collection Route Registry

- Generated: `2026-06-22T11:50:36+00:00`
- Schema version: `collection-routes/v1`
- Routes: `195`

## Status Counts
- `blocked_auth`: 1
- `discovery_only`: 1
- `exhausted`: 1
- `low_yield`: 65
- `manual_only`: 1
- `productive`: 126

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
| sprint_pga_gaunt_moving_finger_trotting_cob_exact_text | productive | Project Gutenberg Australia | exact_plain_text | 18 | 17 | 5 | 1 |  | Scale productive route |
| sprint_pga_dyson_below_and_on_top_mine_ghosts_exact_text | productive | Project Gutenberg Australia | exact_plain_text | 36 | 35 | 6 | 1 |  | Scale productive route |
| sprint_pga_hume_cook_dandenongs_rescan_exact_texts | low_yield | Project Gutenberg Australia | exact_title_html_text | 12 | 11 | 11 | 1 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_project_gutenberg_westbury_australian_fairy_tales_rescan | low_yield | Project Gutenberg | exact_plain_text | 50 | 45 | 6 | 2 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_project_gutenberg_robertson_australian_tales_rescan | low_yield | Project Gutenberg | exact_plain_text | 22 | 18 | 2 | 2 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_project_gutenberg_barry_bunyip_stories_rescan | low_yield | Project Gutenberg | exact_plain_text | 25 | 19 | 1 | 4 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_pga_dyson_below_and_on_top_rescan_02 | low_yield | Project Gutenberg Australia | exact_plain_text | 26 | 21 | 56 | 4 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_moreton_bay_deception_bay_recollect_ocr | low_yield | City of Moreton Bay Libraries | recollect_search_item_ocr | 0 | 0 | 0 | 3 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_project_gutenberg_australian_legendary_tales_exact_text | productive | Project Gutenberg | exact_plain_text | 714 | 700 | 210 | 14 |  | Scale productive route |
| sprint_project_gutenberg_lawson_while_billy_boils_exact_text | productive | Project Gutenberg | exact_plain_text | 18 | 17 | 1 | 1 |  | Scale productive route |
| sprint_project_gutenberg_lawson_over_the_sliprails_exact_text | productive | Project Gutenberg | exact_plain_text | 17 | 15 | 3 | 1 |  | Scale productive route |
| sprint_project_gutenberg_lawson_rising_of_the_court_exact_text | productive | Project Gutenberg | exact_plain_text | 19 | 17 | 10 | 1 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_in_bad_company_exact_text | productive | Project Gutenberg | exact_plain_text | 26 | 24 | 1 | 2 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_old_melbourne_memories_exact_text | productive | Project Gutenberg | exact_plain_text | 17 | 13 | 1 | 1 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_robbery_under_arms_exact_text | productive | Project Gutenberg | exact_plain_text | 20 | 16 | 1 | 4 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_last_chance_exact_text | productive | Project Gutenberg | exact_plain_text | 30 | 24 | 2 | 6 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_babes_in_bush_exact_text | productive | Project Gutenberg | exact_plain_text | 32 | 27 | 9 | 2 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_nevermore_exact_text | productive | Project Gutenberg | exact_plain_text | 25 | 24 | 2 | 1 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_shearing_riverina_exact_text | low_yield | Project Gutenberg | exact_plain_text | 5 | 4 | 0 | 1 |  | Keep as probe/discovery route only |
| sprint_project_gutenberg_baynton_bush_studies_exact_text | productive | Project Gutenberg | exact_plain_text | 9 | 7 | 2 | 1 |  | Scale productive route |
| sprint_project_gutenberg_steele_rudd_on_our_selection_exact_text | productive | Project Gutenberg | exact_plain_text | 9 | 8 | 0 | 1 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_colonial_reformer_vol1_exact_text | productive | Project Gutenberg | exact_plain_text | 16 | 14 | 1 | 1 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_colonial_reformer_vol2_exact_text | productive | Project Gutenberg | exact_plain_text | 17 | 13 | 1 | 3 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_colonial_reformer_vol3_exact_text | productive | Project Gutenberg | exact_plain_text | 19 | 14 | 0 | 4 |  | Scale productive route |
| sprint_slv_federicis_ghost_exact_page | productive | State Library Victoria | exact_public_html_page | 9 | 8 | 4 | 1 |  | Scale productive route |
| sprint_slv_spooky_library_stories_exact_page | productive | State Library Victoria | exact_public_html_page | 14 | 10 | 0 | 4 |  | Scale productive route |
| sprint_adelaide_arcade_history_ghost_exact_page | low_yield | Adelaide Arcade | exact_public_html_page | 7 | 5 | 7 | 2 |  | Keep as probe/discovery route only |
| sprint_project_gutenberg_lawson_days_world_wide_exact_text | productive | Project Gutenberg | exact_plain_text | 22 | 18 | 5 | 2 |  | Scale productive route |
| sprint_project_gutenberg_steele_rudd_dashwoods_exact_text | productive | Project Gutenberg | exact_plain_text | 7 | 6 | 0 | 1 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_plain_living_exact_text | productive | Project Gutenberg | exact_plain_text | 18 | 16 | 0 | 1 |  | Scale productive route |
| sprint_project_gutenberg_clarke_natural_life_exact_text | productive | Project Gutenberg | exact_plain_text | 31 | 26 | 4 | 4 |  | Scale productive route |
| sprint_project_gutenberg_boldrewood_crooked_stick_exact_text | productive | Project Gutenberg | exact_plain_text | 17 | 16 | 0 | 1 |  | Scale productive route |
| sprint_project_gutenberg_hume_hansom_cab_exact_text | productive | Project Gutenberg | exact_plain_text | 23 | 17 | 11 | 3 |  | Scale productive route |
| sprint_museums_victoria_history_probe | low_yield | Museums Victoria | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_geelong_heritage_place_first_probe | low_yield | Geelong Regional Libraries | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_marion_heritage_probe | low_yield | City of Marion | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_libraries_tasmania_eheritage_probe | low_yield | Libraries Tasmania | public_search_page_probe | 5 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_act_heritage_library_probe | low_yield | Libraries ACT | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_anu_open_research_folklore_probe | low_yield | Australian National University | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_slv_catalogue_place_first_probe | low_yield | State Library Victoria | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_prov_collection_place_first_probe | low_yield | Public Record Office Victoria | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_slwa_battye_place_first_probe | low_yield | State Library of Western Australia | public_search_page_probe | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_wa_museum_maritime_place_first_probe | low_yield | Western Australian Museum | public_search_page_probe | 2 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_slsa_place_first_probe | low_yield | State Library of South Australia | public_search_page_probe | 30 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_state_records_sa_archivessearch_probe | low_yield | State Records of South Australia | public_search_page_probe | 1 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_project_gutenberg_franklin_my_brilliant_career_exact_text | productive | Project Gutenberg | exact_plain_text | 23 | 19 | 1 | 3 |  | Scale productive route |
| sprint_project_gutenberg_cambridge_thirty_years_australia_exact_text | productive | Project Gutenberg | exact_plain_text | 13 | 10 | 1 | 3 |  | Scale productive route |
| sprint_project_gutenberg_cambridge_three_miss_kings_exact_text | productive | Project Gutenberg | exact_plain_text | 23 | 17 | 2 | 5 |  | Scale productive route |
| sprint_project_gutenberg_cambridge_sisters_exact_text | productive | Project Gutenberg | exact_plain_text | 13 | 11 | 0 | 2 |  | Scale productive route |
| sprint_project_gutenberg_dyson_gold_stealers_exact_text | productive | Project Gutenberg | exact_plain_text | 16 | 15 | 1 | 0 |  | Scale productive route |
| sprint_project_gutenberg_dyson_roaring_fifties_exact_text | productive | Project Gutenberg | exact_plain_text | 21 | 18 | 2 | 2 |  | Scale productive route |
| sprint_project_gutenberg_furphy_such_is_life_exact_text | productive | Project Gutenberg | exact_plain_text | 26 | 23 | 1 | 1 |  | Scale productive route |
| sprint_project_gutenberg_franklin_some_everyday_folk_exact_text | productive | Project Gutenberg | exact_plain_text | 19 | 18 | 0 | 1 |  | Scale productive route |
| sprint_project_gutenberg_hume_madame_midas_exact_text | productive | Project Gutenberg | exact_plain_text | 21 | 16 | 1 | 4 |  | Scale productive route |
| sprint_project_gutenberg_richardson_australia_felix_exact_text | productive | Project Gutenberg | exact_plain_text | 33 | 26 | 0 | 6 |  | Scale productive route |
| sprint_project_gutenberg_richardson_getting_wisdom_exact_text | productive | Project Gutenberg | exact_plain_text | 22 | 17 | 2 | 4 |  | Scale productive route |
| sprint_project_gutenberg_turner_wonder_child_exact_text | productive | Project Gutenberg | exact_plain_text | 13 | 10 | 0 | 3 |  | Scale productive route |
| sprint_internet_archive_more_australian_legendary_tales_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 17 | 16 | 2 | 0 |  | Scale productive route |
| sprint_internet_archive_spencer_across_australia_vol1_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 16 | 16 | 4 | 0 |  | Scale productive route |
| sprint_internet_archive_mathews_notes_nsw_exact_text | low_yield | Internet Archive | exact_item_metadata_and_djvu_text | 2 | 2 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_internet_archive_calvert_aborigines_wa_exact_text | low_yield | Internet Archive | exact_item_metadata_and_djvu_text | 2 | 2 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_internet_archive_calvert_wa_google_exact_text | low_yield | Internet Archive | exact_item_metadata_and_djvu_text | 2 | 2 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_internet_archive_mathews_sociology_wa_exact_article | low_yield | Internet Archive | exact_item_metadata_and_djvu_text | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_internet_archive_spencer_across_australia_vol2_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 17 | 16 | 5 | 0 |  | Scale productive route |
| sprint_internet_archive_more_australian_legendary_tales_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 29 | 21 | 28 | 4 |  | Scale productive route |
| sprint_internet_archive_spencer_across_australia_vol1_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 11 | 11 | 21 | 0 |  | Scale productive route |
| sprint_internet_archive_spencer_across_australia_vol2_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 68 | 67 | 34 | 0 |  | Scale productive route |
| sprint_internet_archive_mathews_notes_nsw_rescan_02 | low_yield | Internet Archive | exact_item_metadata_and_djvu_text | 0 | 0 | 2 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_internet_archive_calvert_wa_rescan_02 | low_yield | Internet Archive | exact_item_metadata_and_djvu_text | 0 | 0 | 2 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_internet_archive_dawson_victoria_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 32 | 30 | 49 | 2 |  | Scale productive route |
| sprint_internet_archive_smyth_victoria_vol1_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 119 | 107 | 7 | 5 |  | Scale productive route |
| sprint_internet_archive_northern_tribes_central_australia_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 87 | 87 | 34 | 0 |  | Scale productive route |
| sprint_internet_archive_kamilaroi_kurnai_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 32 | 32 | 53 | 0 |  | Scale productive route |
| sprint_internet_archive_native_tribes_sa_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 31 | 30 | 32 | 0 |  | Scale productive route |
| sprint_internet_archive_roth_queensland_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 17 | 15 | 9 | 1 |  | Scale productive route |
| sprint_internet_archive_smyth_victoria_vol2_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 47 | 46 | 35 | 1 |  | Scale productive route |
| sprint_internet_archive_eaglehawk_crow_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 17 | 17 | 31 | 0 |  | Scale productive route |
| sprint_internet_archive_moore_wa_diary_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 38 | 32 | 16 | 5 |  | Scale productive route |
| sprint_internet_archive_fraser_nsw_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 68 | 66 | 43 | 2 |  | Scale productive route |
| sprint_internet_archive_lang_queensland_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 16 | 14 | 26 | 1 |  | Scale productive route |
| sprint_internet_archive_booandik_sa_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 40 | 38 | 5 | 2 |  | Scale productive route |
| sprint_internet_archive_canberra_history_legends_exact_text | productive | Internet Archive | exact_item_metadata_and_djvu_text | 8 | 7 | 1 | 1 |  | Scale productive route |
| sprint_internet_archive_roth_tasmania_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 48 | 46 | 40 | 0 |  | Scale productive route |
| sprint_internet_archive_peck_australian_legends_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 60 | 58 | 29 | 2 |  | Scale productive route |
| sprint_internet_archive_ridley_kamilaroi_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 32 | 32 | 39 | 0 |  | Scale productive route |
| sprint_internet_archive_native_tribes_nt_rescan_02 | productive | Internet Archive | exact_item_metadata_and_djvu_text | 86 | 85 | 5 | 0 |  | Scale productive route |
| sprint_mapfirst_gutenberg_clarke_natural_life_port_arthur | low_yield | Project Gutenberg | exact_place_filtered_text | 3 | 3 | 2 | 0 |  | Keep as probe/discovery route only |
| sprint_mapfirst_ia_suttor_fishers_ghost_campbelltown | low_yield | Internet Archive | exact_place_filtered_text | 0 | 0 | 2 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_mapfirst_gutenberg_australian_fairy_tales_blue_mountains | low_yield | Project Gutenberg | exact_place_filtered_text | 2 | 1 | 0 | 1 |  | Keep as probe/discovery route only |
| sprint_mapfirst_ia_lumholtz_herbert_river | productive | Internet Archive | exact_place_filtered_text | 7 | 6 | 13 | 0 |  | Scale productive route |
| sprint_mapfirst_ia_lake_george_devil_exact_text | low_yield | Internet Archive | exact_place_filtered_text | 1 | 1 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_mapfirst_gutenberg_hume_madame_midas_ballarat | low_yield | Project Gutenberg | exact_place_filtered_text | 12 | 0 | 0 | 12 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_mapfirst_gutenberg_hume_hansom_cab_melbourne | low_yield | Project Gutenberg | exact_place_filtered_text | 2 | 0 | 0 | 2 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_mapfirst_gutenberg_richardson_australia_felix_ballarat | low_yield | Project Gutenberg | exact_place_filtered_text | 5 | 1 | 0 | 4 |  | Keep as probe/discovery route only |
| sprint_mapfirst_gutenberg_lawson_while_billy_bourke | low_yield | Project Gutenberg | exact_place_filtered_text | 2 | 1 | 0 | 1 |  | Keep as probe/discovery route only |
| sprint_mapfirst_gutenberg_lawson_while_billy_mudgee | low_yield | Project Gutenberg | exact_place_filtered_text | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_mapfirst_gutenberg_lawson_on_track_gulgong | low_yield | Project Gutenberg | exact_place_filtered_text | 1 | 0 | 0 | 1 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_mapfirst_ia_lawson_joe_wilson_bathurst | low_yield | Internet Archive | exact_place_filtered_text | 0 | 0 | 0 | 0 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_abc_placefirst_national_haunted_sites | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 64 | 16 | 17 | 58 |  | Scale productive route |
| sprint_abc_placefirst_tasmania_port_arthur_hobart | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 15 | 10 | 0 | 14 |  | Scale productive route |
| sprint_abc_placefirst_sa_vic_gaol_asylum_theatre | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 36 | 6 | 0 | 49 |  | Scale productive route |
| sprint_abc_placefirst_wa_act_qld_nsw_sites | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 52 | 11 | 9 | 49 |  | Scale productive route |
| sprint_abc_placefirst_wa_modern_haunted_sites_02 | low_yield | Australian Broadcasting Corporation | abc_algolia_place_search | 44 | 3 | 2 | 92 |  | Keep as probe/discovery route only |
| sprint_abc_placefirst_nt_modern_haunted_sites_02 | low_yield | Australian Broadcasting Corporation | abc_algolia_place_search | 48 | 1 | 0 | 189 |  | Keep as probe/discovery route only |
| sprint_abc_placefirst_sa_tas_modern_sites_02 | low_yield | Australian Broadcasting Corporation | abc_algolia_place_search | 48 | 5 | 2 | 120 |  | Keep as probe/discovery route only |
| sprint_abc_exact_discovered_wa_sa_tas_modern_03 | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 28 | 9 | 0 | 45 |  | Scale productive route |
| sprint_abc_exact_discovered_national_modern_03 | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 40 | 18 | 0 | 36 |  | Scale productive route |
| sprint_abc_exact_wa_tas_additional_modern_04 | low_yield | Australian Broadcasting Corporation | abc_algolia_place_search | 3 | 1 | 1 | 8 |  | Keep as probe/discovery route only |
| sprint_abc_exact_act_vic_tas_known_sites_04 | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 16 | 16 | 2 | 5 |  | Scale productive route |
| sprint_abc_exact_qld_nsw_known_sites_04 | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 10 | 10 | 1 | 11 |  | Scale productive route |
| sprint_abc_exact_wa_york_oakabella_retry_05 | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 10 | 6 | 3 | 14 |  | Scale productive route |
| sprint_abc_exact_sa_tas_known_sites_05 | low_yield | Australian Broadcasting Corporation | abc_algolia_place_search | 8 | 5 | 2 | 26 |  | Keep as probe/discovery route only |
| sprint_abc_exact_nt_modern_sites_05 | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 12 | 9 | 8 | 56 |  | Scale productive route |
| sprint_abc_exact_modern_bonus_sites_05 | productive | Australian Broadcasting Corporation | abc_algolia_place_search | 18 | 16 | 7 | 9 |  | Scale productive route |
| sprint_abc_exact_public_pages_06 | productive | Australian Broadcasting Corporation | public_page_place_text | 15 | 8 | 1 | 6 |  | Scale productive route |
| sprint_abc_exact_public_pages_nt_qld_07 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 3 | 2 | 0 | 1 |  | Keep as probe/discovery route only |
| sprint_abc_australias_most_haunted_places_08 | productive | Australian Broadcasting Corporation | public_page_place_text | 6 | 6 | 0 | 0 |  | Scale productive route |
| sprint_abc_australias_most_haunted_places_rescan_09 | productive | Australian Broadcasting Corporation | public_page_place_text | 6 | 6 | 0 | 0 |  | Scale productive route |
| sprint_abc_ghosthunters_picton_woodford_10 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 2 | 2 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_abc_qld_ghostbuster_places_rescan_11 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 3 | 0 | 0 | 3 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_abc_exact_public_pages_rescan_12 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 3 | 2 | 0 | 1 |  | Keep as probe/discovery route only |
| sprint_abc_exact_site_units_rescan_13 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 4 | 2 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_abc_richmond_bridge_exact_14 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 1 | 0 | 0 | 1 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_abc_richmond_bridge_exact_15 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 1 | 0 | 0 | 1 | low_yield_or_discovery_only | Keep as probe/discovery route only |
| sprint_abc_richmond_bridge_exact_16 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 1 | 1 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_adelaide_gaol_ghostly_sightings_exact_17 | productive | Adelaide Gaol |  | 12 | 8 | 8 | 4 |  | Scale productive route |
| sprint_adelaide_gaol_william_ashton_section_18 | low_yield | Adelaide Gaol |  | 1 | 1 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_abc_modern_wa_tas_sa_site_units_19 | productive | Australian Broadcasting Corporation | public_page_place_text | 11 | 9 | 0 | 1 |  | Scale productive route |
| sprint_abc_modern_wa_tas_sa_site_units_20 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 5 | 5 | 0 | 0 |  | Keep as probe/discovery route only |
| sprint_abc_hobart_distinct_ghost_places_21 | low_yield | Australian Broadcasting Corporation | public_page_place_text | 5 | 2 | 0 | 3 |  | Keep as probe/discovery route only |
| sprint_abc_hobart_named_ghost_sections_22 | low_yield | Australian Broadcasting Corporation |  | 3 | 3 | 0 | 0 |  | Keep as probe/discovery route only |
