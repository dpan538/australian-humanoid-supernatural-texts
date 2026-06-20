# V2 Migration Report

- Generated: `2026-06-20T02:04:55+00:00`
- Schema version: `2.0.0`
- Legacy rows: 985
- Migrated source items: 985
- Migrated narrative units: 916
- Legacy mappings: 985
- Unmapped legacy rows: 0
- Entity labels: 985
- Narrative locations: 920

## Notes
- The legacy `records` table is intact.
- Automated migration never assigns `analysis_ready`.
- Academic metadata is migrated as catalogue/source-pointer material unless manually reviewed later.
- Source labels are preserved separately from entity concepts.
- Publication/source geography is not silently converted into event geography.
