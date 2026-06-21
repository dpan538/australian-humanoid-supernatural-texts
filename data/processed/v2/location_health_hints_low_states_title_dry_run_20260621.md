# Location Health Hint Pass

- Generated: `2026-06-21T16:36:25+00:00`
- Hints: `/Users/jarlgiovanni/Desktop/bigfoot_research/config/ayr_location_health_hints.yml`
- Dry run: `True`
- Network geocoding disabled: `False`
- States: `['ACT', 'NT', 'SA', 'TAS', 'VIC', 'WA']`

## Counts
- records_examined: 1097
- records_with_hint_match: 5
- geocoded_places: 4
- attached_locations: 4
- skipped_existing_strict: 880
- skipped_ungeocoded: 1

## Example Attachments
- record `52` (1985): Darriman, VIC (-38.40965, 146.89879) [title_place_pattern] -- Darriman, Victoria 1985
- record `223` (2000): Billabong, VIC (-37.25162, 146.81683) [title_place_pattern] -- Billabong, Victoria 2000
- record `613` (1987): Brindabella, ACT (-35.30930, 149.00630) [curated_hint] -- Wee Jasper, New South Wales 1987
- record `677` (1882): Augusta, WA (-34.31561, 115.16059) [curated_hint] -- 1882 - Victoria Express, Gorilla Shot

## Policy
- Only curated source-visible place aliases are used.
- State-only, country-only, publication-location, and tourism-only signals are not promoted to strict map points by this script.
- Coordinate resolution uses cached Nominatim/OpenStreetMap results with a project User-Agent and rate limit.
