# Collection Sprint Status

- Generated: `2026-06-22T04:54:27+00:00`
- Run id: `collection_sprint_20260622_002`
- Stage directory: `/Users/jarlgiovanni/Desktop/bigfoot_research/data/interim/collection_sprint/collection_sprint_20260622_002`
- Starting public records: `1217`
- Ending public records: `1380`
- Net-new public records: `163`
- Starting map flags: `832`
- Ending map flags: `891`
- Net-new map flags: `59`
- Candidates processed: `483`
- Context/lead staged: `0`
- Suppressed/rejected staged: `2`
- Duplicate staged: `30`
- Unique map queue rows promoted: `25`
- Remaining gap to 2800: `1420`
- Remaining gap to 1200 map flags: `309`
- Map invariant ok: `True`

## Records by Source Organisation
- Internet Archive: 15
- Internet Sacred Text Archive: 45
- Project Gutenberg Australia: 22
- Wikisource: 81

## Records by Source Family
- public_domain_ebook: 22
- public_domain_transcribed_book: 126
- repository_full_text: 15

## Records by Jurisdiction
- NSW: 39
- NT: 45
- QLD: 15

## Records by Narrative Type
- apparition_account: 24
- descriptive_belief_record: 23
- giant_or_ogre_narrative: 6
- retelling_or_adaptation: 19
- spirit_person_narrative: 91

## Per-Route Yield

| route_id | family | processed | accepted | context | rejected | duplicates | map_candidates | runtime_s | stop_reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| sprint_internet_archive_roth_queensland_exact_text | repository_institutional_full_text | 30 | 30 | 0 | 0 | 4 | 0 | 11.8 | route_candidate_limit_or_source_exhausted |
| sprint_ista_central_australia_exact_texts | structured_public_domain_books | 88 | 84 | 0 | 4 | 6 | 0 | 5.6 | route_candidate_limit_or_source_exhausted |
| sprint_ista_northern_australia_exact_texts | structured_public_domain_books | 32 | 32 | 0 | 0 | 10 | 0 | 3.1 | route_candidate_limit_or_source_exhausted |
| sprint_map_queue_geocode_verification | place_first_map_records | 100 | 25 | 0 | 0 | 0 | 25 | 131.6 | map_target_reached |
| sprint_pga_australian_fairy_tales_exact_texts | structured_public_domain_books | 44 | 44 | 0 | 0 | 6 | 0 | 18.1 | route_candidate_limit_or_source_exhausted |
| sprint_sa_history_network_directory_probe | local_archive_historical_society | 2 | 0 | 0 | 0 | 0 | 0 | 3.0 | probe_directory_or_search_page_discovery_only |
| sprint_territory_stories_public_probe | repository_institutional_full_text | 0 | 0 | 0 | 0 | 0 | 0 | 2.2 | probe_directory_or_search_page_discovery_only |
| sprint_victorian_collections_story_probe | local_archive_historical_society | 0 | 0 | 0 | 0 | 0 | 0 | 0.3 | probe_error:HTTPError |
| sprint_wikisource_euahlayi_exact_texts | structured_public_domain_books | 69 | 69 | 0 | 0 | 16 | 0 | 5.8 | route_candidate_limit_or_source_exhausted |
| sprint_wikisource_southeast_exact_texts | structured_public_domain_books | 118 | 112 | 0 | 6 | 20 | 0 | 5.4 | accepted_target_reached; route_candidate_limit_or_source_exhausted |

## Productive Routes

- sprint_internet_archive_roth_queensland_exact_text
- sprint_ista_central_australia_exact_texts
- sprint_ista_northern_australia_exact_texts
- sprint_map_queue_geocode_verification
- sprint_pga_australian_fairy_tales_exact_texts
- sprint_wikisource_euahlayi_exact_texts
- sprint_wikisource_southeast_exact_texts

## Exhausted or Discovery-Only Routes

- sprint_sa_history_network_directory_probe
- sprint_territory_stories_public_probe
- sprint_victorian_collections_story_probe
