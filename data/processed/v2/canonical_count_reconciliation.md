# Canonical Count Reconciliation

- Generated: `2026-07-05T07:40:49+00:00`
- Canonical frontend public records: `4265`
- Canonical frontend public map rows: `1593`
- DB legacy mapped-like rows: `4393`
- count_conflict_resolved: `true`
- Resolution reason: 4393 mapped-like rows partition into 767 frontend matches and 3626 non-frontend/internal rows; 826 frontend map rows are frontend-only relative to V2 narrative_locations, yielding the 2800-row net difference

## Population Counts
- `canonical_frontend_public_records`: 4265 (public/data/frontend-data.json.records)
- `canonical_frontend_public_map_rows`: 1593 (public/data/frontend-data.json.map_points)
- `db_legacy_mapped_like_rows`: 4393 (data/exports/v2/narrative_locations_review.csv)
- `db_public_records`: 4638 (records)
- `db_internal_location_rows`: 4393 (narrative_locations)
- `db_candidate_location_rows`: 0 (collection_candidates)
- `db_geocode_review_rows`: 6 (geocode_review_queue)

## Mapped-Like Row Partitions
- `DUPLICATE_LOCATION_ROW`: 258
- `FRONTEND_PUBLIC_MAP`: 767
- `INTERNAL_LOCATION_ROW`: 3125
- `LEGACY_NONPUBLIC_LOCATION`: 230
- `SUPPRESSED_LOCATION_ROW`: 13

## Count Conflict

The 1,593 vs 4,393 discrepancy is explained by partitioning non-frontend/internal mapped-like rows.

## Safety Note
- Only `FRONTEND_PUBLIC_MAP` rows may be scored as public map cleanup candidates.
