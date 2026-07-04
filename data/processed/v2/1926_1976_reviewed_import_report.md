# 1926-1976 Reviewed Gap Candidate Import

- Generated: `2026-07-04T14:09:21+00:00`
- Run id: `gap_1926_1976_reviewed_import_20260704`
- Accepted rows loaded from source files: `989`
- Rows kept after production duplicate filters: `456`
- Record-only rows: `69`
- Rows with exporter-eligible map locations: `387`
- Promoted records this run: `0`
- Already promoted for this run: `456`
- Existing location verification rows repaired: `0`
- Promoted coding/entity label rows synced: `912`

## Source Counts
| source_type | records | mapped_candidates |
| --- | ---: | ---: |
| public_web_yowie_report_map | 350 | 350 |
| institutional_media_page | 41 | 23 |
| public_books_metadata_openlibrary | 33 | 0 |
| public_web_yowie_state_report_index | 21 | 8 |
| public_books_metadata_internet_archive | 6 | 6 |
| public_wikidata_entity_metadata | 5 | 0 |

## Raw Candidate Status
- raw_status:accepted: 1524
- raw_status:lead_only: 1208
- duplicate_within_import_files: 535
- raw_status:rejected: 320
- raw_status:duplicate_existing_record: 215

## Duplicate Filters
- existing_run_reused_for_idempotent_report: 456

## Production Interpretation
- `mapped` rows remain public display locations for source records, not proof, habitats, or populations.
- HauntedPlaces directory rows and non-strict OpenAlex/Crossref rows are excluded from this import.
- Figure labels are normalized within this reviewed import batch to avoid display-card fragmentation from case/plural variants.
- OpenLibrary and Wikidata rows are imported as records-only unless an independently reviewed display location exists later.
- AYR map/index coordinates are normalized as source-visible public display locations with explicit non-verification notes.
- Fisher's Ghost Internet Archive rows are retained as a micro-batch with duplicate/enrichment risk noted in the filter audit.
