# AYR Public Record Card Collection Report

## Execution Context
- Run: `ayr_public_reports_round_001`
- Started: `2026-06-19T10:41:06+00:00`
- Finished: `2026-06-19T10:43:24+00:00`
- Source: [Australian Yowie Research](https://www.yowiehunters.com.au/)
- Robots/publicness check: robots.txt checked; public state/report paths are not disallowed.
- Starting record count: 13
- Ending record count immediately after AYR insert: 213
- Current frontend/export record count after legacy metadata-lead cleanup: 208
- Legacy lead-only records removed after run: 5
- Target new card-ready records: 200
- Inserted new card-ready records: 200
- Candidate/status CSV: `data/interim/ayr_record_candidates.csv`

## Card-Ready Gate
A page was inserted only when it supplied enough display data for the record card: year, title or Yowie figure, public source URL, Australian state/territory, and a concise objective summary. Search leads and pages missing those fields were skipped.

Post-run SQL checks confirm that all 200 AYR records have the fields required by the record-card overlay: year, title, URL, snippet, source identifier, coding row, and at least one linked state/place record. Lead-only rows are not exported as frontend records.

## New Records By State/Territory
- WA: 10
- NT: 9
- SA: 7
- QLD: 65
- NSW: 65
- VIC: 40
- TAS: 4
- ACT: 0

## New Records By Date Band
- backsearch_1803_1841: 0
- anchor_1842_1875: 2
- expansion_1876_1969: 5
- modern_1970_present: 193
- undated: 0

## Skipped Candidates
- none

## Coverage Note
The AYR state pages are not evenly distributed. NSW, QLD, and VIC have many more public report pages than WA, SA, NT, and TAS, so this run exhausts low-availability states first and fills the 200-record target from higher-availability states. The imbalance should be addressed in the next round with source-specific searches rather than by fabricating regional symmetry.
