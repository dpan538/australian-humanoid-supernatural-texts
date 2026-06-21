# Location Health Hint Pass

- Generated: `2026-06-21T16:30:16+00:00`
- Hints: `/Users/jarlgiovanni/Desktop/bigfoot_research/config/ayr_location_health_hints.yml`
- Dry run: `True`
- Network geocoding disabled: `True`
- States: `['ACT', 'NT', 'SA', 'TAS', 'VIC', 'WA']`

## Counts
- records_examined: 1097
- records_with_hint_match: 2
- geocoded_places: 0
- attached_locations: 0
- skipped_existing_strict: 880
- skipped_ungeocoded: 2

## Example Attachments

## Policy
- Only curated source-visible place aliases are used.
- State-only, country-only, publication-location, and tourism-only signals are not promoted to strict map points by this script.
- Coordinate resolution uses cached Nominatim/OpenStreetMap results with a project User-Agent and rate limit.
