# V2 Collection Progress

- Generated: `2026-06-21T17:13:52+00:00`
- Accepted net-new source items: 58
- Target: 2800
- Remaining: 2742
- Strict geography only: `False`

## Candidate Status
- accepted: 58
- duplicate: 38
- lead_only: 1149
- rejected: 44

## Current Limitation
- This run stages leads and/or manually verified candidates only.
- Metadata-only, unresolved leads, duplicate URLs, restricted records, controls, and exclusions do not count toward the 2800 accepted target.
- In strict-geography mode, candidates without verified latitude/longitude, locality precision, geocode source, coordinate evidence, duplicate status, and quality class A/B/C are rejected.
- Outside strict-geography mode, substantive public-text candidates with broad or unresolved geography may be accepted for dashboard/density review surfaces only; they are excluded from the map until strict coordinates are verified.
- Trove article-level collection requires a supplied `TROVE_API_KEY` or manual verified imports.
- Internet Archive strict-map items require public text/OCR, source label in text, and a strict gazetteer place. Internet Archive public-display items may use broad geography but must still expose public text/OCR and source-label evidence.
- Seeded public-web rows count only when the configured public page or manual public excerpt verifies both the source label and the strict place.
