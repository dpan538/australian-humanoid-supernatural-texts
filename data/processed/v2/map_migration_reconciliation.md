# Map Migration Reconciliation

- Compared old export: `16a407da7d11ec4e531a31e89417a7fe82c30f9b:public/data/frontend-data.json`
- Compared current export: `public/data/frontend-data.json`

## Counts

- Previous mapped records/points: `894`
- Current mapped records/points: `832`
- Old synthetic accepted-candidate map points resolved through promotion and still mapped: `12`
- Previously mapped rows not mapped now after candidate-id reconciliation: `62`

## Disappearance Reasons

| reason | rows |
|---|---:|
| invalid_or_unverified_coordinate | 62 |

## Finding

All disappeared rows still have `record_locations` rows, but their coordinate status is `source_named_place_needs_geocode`. The canonical exporter is correctly excluding these from public map flags because coordinates are not verified. No promotion repair was applied.

## Project Gutenberg Australia Batch Audit

- Project Gutenberg Australia records audited: `30`
- Duplicate external IDs: `0`
- Bare metadata rows detected: `0`
- Distinctness basis: every row uses a distinct `pga:<ebook>:<section-title>` external ID and a section-specific evidence summary from a full-text story unit.

### Source Items

| source item | records |
|---|---:|
| Australian Legends / Project Gutenberg Australia | 11 |
| Australian Legendary Tales / Project Gutenberg Australia | 13 |
| More Australian Legendary Tales / Project Gutenberg Australia | 6 |

### Narrative Types

| narrative type | records |
|---|---:|
| traditional_narrative | 16 |
| spirit_person_narrative | 11 |
| giant_or_ogre_narrative | 3 |

## Row-Level Export

- CSV: `data/exports/v2/map_migration_reconciliation.csv`
