# Frontend Data Contract V2

The visual frontend remains intact. V2 only adds a normalized data contract at:

`public/data/frontend-data/v2.json`

Required top-level fields:

- `schema_version`
- `generated_at`
- `summary_counts`
- `counts`
- `map_layers`
- `timeline_fields`
- `narratives`
- `source_items`
- `entity_labels`
- `entity_concepts`
- `narrative_source_links`
- `public_note`

Map layers:

- `alleged_event_location`
- `apparition_location`
- `legend_associated_place`
- `narrative_setting`
- `cultural_association_region`
- `publication_location`
- `uncertain_or_broad_location`

Publication locations must never be silently displayed as event locations. The interface should state that map data represents narrative geography, source geography, or alleged event geography, not verified supernatural distribution.

Timeline fields:

- `event_date`
- `earliest_attestation`
- `publication_date`
- `retelling_date`
- `circulation_period`

