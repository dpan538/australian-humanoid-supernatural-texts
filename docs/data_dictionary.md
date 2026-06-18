# Data Dictionary

The database lives at `data/processed/australian_humanoid_figures.sqlite`.

## sources

Source registry for public data locations and planned collection channels.

- `source_id`: primary key.
- `source_name`: human-readable source name.
- `source_type`: source class, such as `trove_newspaper`, `trove_magazine`, `nla_catalogue`, `aiatsis_public_catalogue`, `andc`, `google_trends`, `wikimedia_pageviews`, `modern_web`, or `manual`.
- `base_url`: public source URL when applicable.
- `access_method`: manual, API, CSV, or planned collection path.
- `publicness_level`: open/public/restricted status.
- `ethics_notes`: source-specific caution notes.

## figures

Controlled list of core figures, validation candidates, excluded controls, and non-core controls.

- `canonical_name`: preferred project label.
- `cluster`: broad grouping, such as `yowie_yahoo_hairy_man`, `broader_humanoid_spirit`, `validation_queue`, or `excluded_control`.
- `tier`: inclusion strength or boundary status.
- `include_status`: `include_v1`, `validate_before_include`, `exclude_core`, or `control_only`.
- `humanoid_degree`: default humanoid relation.
- `ontology_default`: initial ontology label for review.
- `involves_indigenous_knowledge`: integer flag.
- `sensitivity_notes`: cautions for collection and coding.
- `description`: short scope note.

## aliases

Search and matching forms linked to figures.

- `alias`: exact phrase, variant, descriptor, or noise-sensitive term.
- `alias_type`: `exact`, `spelling_variant`, `phrase`, `historical_descriptor`, or `noise_sensitive`.
- `search_priority`: higher values are considered first during matching.
- `notes`: search or interpretation notes.

## queries

Planned search rows generated from config.

- `query_string`: source-facing search string.
- `query_type`: `exact_phrase`, `constrained_boolean`, `fuzzy_variant`, `negative_control`, or `attention_series`.
- `date_start`, `date_end`: text date bounds.
- `expected_noise_level`: low, medium, high, or extreme.
- `status`: normally `planned`.
- `notes`: generated rationale.

## records

Imported source records. This table stores metadata and the path to saved raw text, but does not decide final relevance.

## record_alias_matches

Rule-based alias matches found in imported title, snippet, or raw text. These matches are evidence for review, not final truth.

## coding

Human-review queue fields and initial system coding. `relevance_code` defaults to `needs_review` unless an obvious noise pattern is detected.

## dedupe_groups and record_dedupe

Duplicate annotations. Records are never deleted. Groups indicate exact URL duplicates, same title/year/publication, or near duplicates.

## attention_series

Future attention metrics from Google Trends or Wikimedia Pageviews. Empty exports are valid before collection.

## locations

Reviewed place and region labels used for conservative geographic coding.

- `place_name`: normalised place or region name.
- `region`: broader regional label when useful.
- `state_territory`: Australian state or territory abbreviation where applicable.
- `country`: defaults to Australia.
- `latitude`, `longitude`: present only for specific places where the project gazetteer has a reviewed coordinate.
- `location_type`: country, state_or_territory, town, locality, broad_region, or uncertain locality.
- `geocode_source`: how the location was normalised.
- `verification_status`: `verified_place`, `verified_region`, `verified_country_scope`, `broad_region_only`, or `needs_review`.
- `notes`: caution or review notes.

## record_locations

Join table between records and locations. This is evidence for review, not final spatial analysis.

- `record_id`: linked record.
- `location_id`: linked location.
- `relation_type`: currently `mentioned_place`.
- `evidence_text`: short context supporting the match.
- `confidence`: high, medium, or low.
- `notes`: usually a reminder that human review is required.

## collection_runs

Audit log for collection rounds.

- `run_name`: short identifier, such as `public_round_001`.
- `run_started_at`, `run_finished_at`: UTC timestamps.
- `scope_notes`: what the round attempted.
- `methods`: sources and retrieval methods.
- `limitations`: known gaps, such as missing API keys or metadata-only leads.

