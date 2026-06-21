# V2 Data Cleaning Report

- Generated: `2026-06-21T09:14:30+00:00`
- Schema version: `2.0.0`

## Cleaning Rules Applied
- Canonical URLs are generated with lower-cased hostnames and tracking parameters removed.
- Source labels are preserved in `entity_labels` and not silently normalized to Yowie.
- Source/publication metadata is separated from narrative/event fields.
- Automated migration marks records as display/review states only, never analysis-ready.
