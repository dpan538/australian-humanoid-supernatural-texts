# Migration Guide

Run the V2 migration in this order:

```bash
make snapshot-legacy
make migrate-v2
make export-v2
make audit-v2
make validate-v2
make export-frontend
make test
make frontend-build
```

The legacy `records` table is kept intact. V2 tables are additive and connected through `legacy_record_mappings`.

Every legacy record must map to one `source_item_id`. Some legacy records also map to a `narrative_id`; lead-only, metadata-only, control, and exclusion rows may not.

The migration is deterministic and idempotent. Running it repeatedly should not duplicate mappings.

Automated migration never sets `analysis_ready`.

