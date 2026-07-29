# Source Route Atlas Seed

`config/source_registry.yml` is the canonical machine-readable route atlas. This seed document summarizes the route classes reviewers should expect.

| Route group | Examples | Mode |
|---|---|---|
| National library and newspaper metadata | `trove_newspapers_gazettes`, `trove_magazines_newsletters`, `nla_catalogue` | Semi-automated metadata-first when API/robots/terms allow |
| National archive and public broadcast catalogues | `naa_recordsearch`, `nfsa_collection`, `abc_archives_public_pages`, `australian_screen_online` | Semi-automated or manual catalogue review |
| Indigenous/community-sensitive catalogues | `aiatsis_collection_search`, `austlang` | Manual-only sensitive review |
| Gazetteers and place authorities | `composite_gazetteer_australia`, `gnaf_address_file`, `nt_place_names_register` | Discovery/authority only, not evidence |
| Repository and access platforms | `internet_archive_access_platform`, `project_gutenberg_australia_access_platform`, `wikisource_access_platform`, `pandora_web_archive` | Evidence only if original source is decomposed |
| Scholarly/repository metadata | `openalex_crossref_discovery_only`, `research_data_australia`, `informit_metadata_only`, `worldcat_metadata_only`, `openlibrary_metadata_only`, `anu_open_research` | Discovery-only unless a public original is identified |
| State libraries and archives | `slnsw_catalogue`, `slq_one_search`, `slv_catalogue`, `slwa_catalogue`, `slsa_catalogue`, `library_archives_nt_catalogue`, `libraries_tasmania_catalogue`, `act_heritage_library` | Metadata-first, review before acceptance |
| Local history serials and societies | `history_west_rwahs`, `south_australian_history_network`, `historical_society_nt`, `tasmanian_historical_research_association`, `canberra_district_historical_society` | Mostly manual or semi-automated lead review |
| Council local studies | `city_of_sydney_archives`, `fremantle_history_centre`, `city_of_adelaide_archives`, `darwin_city_libraries_local_history`, `alice_springs_public_library_local_history` | Semi-automated metadata or manual review |
| Heritage registers and trusts | `wa_heritage_inherit`, `sa_heritage_places_database`, `nt_heritage_register`, `heritage_tasmania_register`, `act_heritage_register`, National Trust routes | Public summary review; heritage address alone is not a map point |
| Museums and public history sites | `wa_museum_collections`, `south_australian_museum_archives`, `magnt_collections`, `port_arthur_historic_site`, `canberra_museum_gallery`, `australian_war_memorial_collection` | Public metadata review; sensitive collection routes manual-only |

Route modes:

- Automated: API metadata routes with credentials and explicit allowed use, currently only narrow Trove metadata probing.
- Semi-automated: catalogue/search routes where dry-run tasks and metadata review are safe, but content fetch is conservative.
- Manual-only: oral history, Indigenous/community-sensitive, or unclear terms routes.
- Discovery-only: aggregators, authority files, repository metadata, and access platforms without decomposed originals.
