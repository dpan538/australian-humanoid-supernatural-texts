# Strict Geography Policy

- Generated checkpoint: strict map repair, 2026-06-20
- Current frontend records: 985
- Current strict geocoded map points: 1
- Current source-named place records needing geocoding: about 901 location rows

## Decision

The public map should display only records with strict public geographic evidence:

- verified latitude and longitude; or
- a publicly named locality that has passed geocoding and review.

State-level, broad-region, publication-location, and inferred display placements must not appear as record points. They can remain in review tables and record cards, but not as map flags.

## Visual Rule

Each mapped record must correspond to one independent clickable flag. The flag position must come from geographic coordinates, not an artificial in-state layout. Flag color is keyed to source type so mixed source families remain readable in dense areas.

## Collection Implication

The next corpus target should prioritize geospatially healthy records rather than raw volume. A smaller corpus of 2,000 to 3,000 accepted records with strict location evidence has higher research value than 5,000 weakly localized records.

## Next Health Targets

- Convert at least 500 existing source-named place records into reviewed locality-level coordinates.
- Require all newly accepted map-visible records to have source title, source URL or identifier, date note, narrative type, source label, and reviewed location role.
- Keep non-geocoded records in review/export tables, but do not render them as map points.
