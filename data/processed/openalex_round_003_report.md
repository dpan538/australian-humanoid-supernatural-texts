# OpenAlex Public Metadata Collection Report

## Execution Context
- Run: `openalex_public_metadata_round_003`
- Started: `2026-06-19T15:36:36+00:00`
- Finished: `2026-06-19T15:38:09+00:00`
- Starting record count: 707
- Ending record count before noise cleanup: 792
- Target new card-ready metadata records: 85
- Inserted candidate metadata records before cleanup: 85
- Retained card-ready OpenAlex records after Yahoo/noise cleanup: 56
- Removed noise records after audit: 29

## Guardrails
- OpenAlex records are public metadata, not collected full text.
- Region fields are figure-associated review signals, not verified event places.
- Obvious high-noise matches such as Cadbury Yowie, Yowie Bay, biomedical Mamu-B, and unrelated Yahoo items are skipped.

## Retained Records By State/Territory Signal
- UNKNOWN: 6
- WA: 22
- QLD: 19
- VIC: 5
- NT: 3
- ACT: 1

## Retained Records By Figure
- Wandjina: 20
- Quinkan: 16
- Yowie: 6
- Nargun: 4
- Mamu: 4
- Yara-ma-yha-who: 2
- Pangkarlangu: 2
- Mimih: 1
- Hairy Man: 1

## New Records By Date Band
- modern_1970_present: 82
- expansion_1876_1969: 2
- anchor_1842_1875: 1

## Skipped
- duplicate_existing_record: 211
- noise:SIV: 1

## Cleanup Note
The initial OpenAlex pass admitted 29 unrelated Yahoo records. Those rows were
removed from the SQLite database and are not counted in current exports,
frontend data, or coverage audits.
