# Location Health Hint Pass

- Generated: `2026-06-21T16:40:12+00:00`
- Hints: `/Users/jarlgiovanni/Desktop/bigfoot_research/config/ayr_location_health_hints.yml`
- Dry run: `True`
- Network geocoding disabled: `True`
- States: `['ACT', 'NT', 'SA', 'TAS', 'VIC', 'WA']`

## Counts
- records_examined: 1097
- records_with_hint_match: 3
- geocoded_places: 2
- attached_locations: 2
- skipped_existing_strict: 880
- skipped_ungeocoded: 1

## Example Attachments
- record `52` (1985): Darriman, VIC (-38.40965, 146.89879) [title_place_pattern] -- Darriman, Victoria 1985
- record `223` (2000): Billabong, VIC (-37.25162, 146.81683) [title_place_pattern] -- Billabong, Victoria 2000

## Policy
- Only curated source-visible place aliases are used.
- State-only, country-only, publication-location, and tourism-only signals are not promoted to strict map points by this script.
- Coordinate resolution uses cached Nominatim/OpenStreetMap results with a project User-Agent and rate limit.
