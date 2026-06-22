# Frontend Launch Smoke Test

Generated: 2026-06-22T15:50:48+00:00

- Localhost URL: http://localhost:3000
- Server PID: 97225
- Server start time: Mon Jun 22 23:33:18 2026
- Log path: data/processed/v2/localhost_dev_server.log
- Public records: 3752
- Map flags: 1200
- Map points: 1200
- Mapped record count: 1200
- Result: PASS

## Route Status
- /: HTTP 307
- /dashboard: HTTP 200
- /map: HTTP 200
- /density: HTTP 200
- /source: HTTP 200
- /about: HTTP 200

## Desktop QA
- /dashboard: overflow=False, undefined/null text=False, buttons=35, links=3
- /map: overflow=False, undefined/null text=False, buttons=8, links=3
- /density: overflow=False, undefined/null text=False, buttons=8, links=3
- /source: overflow=False, undefined/null text=False, buttons=0, links=4
- /about: overflow=False, undefined/null text=False, buttons=0, links=4

## Mobile QA
- /dashboard: overflow=False, undefined/null text=False, buttons=35, links=3
- /map: overflow=False, undefined/null text=False, buttons=8, links=3
- /density: overflow=False, undefined/null text=False, buttons=8, links=3
- /source: overflow=False, undefined/null text=False, buttons=0, links=4
- /about: overflow=False, undefined/null text=False, buttons=0, links=4

## View Findings
- Dashboard: total record and mapped counts match export; track rows contain final public records.
- Map: 1,200 SVG flag elements render; 20 sampled flags opened record overlays; map count matches export.
- Density: all date bands render, including explicit Undated; date-band total reconciles to 3752.
- Source: source rollup reconciles to 3752; source list is scrollable.
- About: current scope language renders; no active 2,800 launch target text observed.
- Console/runtime errors: 0.
- Previous/next controls: present and changed selected record.
- Escape closes overlays: yes.
- Mobile navigation: usable.

## Defects Fixed
- Added explicit undated date band to frontend export so date-band totals reconcile with 3,752 public records.

## Unresolved Defects
- None material found in smoke pass.

## Sample Coverage
- 20 mapped records sampled: 853, 637, 638, 640, 641, 44, 2116, 855, 1760, 1768, 1769, 1778, 3720, 3724, 643, 644, 84, 646, 604, 647
- 20 unmapped records sampled: 854, 636, 1059, 2085, 2086, 2087, 2088, 2089, 2090, 2091, 2092, 2093, 2094, 2095, 2096, 2097, 2098, 2099, 2100, 2101
- Source organisations sampled: Australian Yowie Research, Internet Archive, Project Gutenberg Australia, Project Gutenberg, Marriner Group, Internet Sacred Text Archive, Wikisource, OpenAlex
- Represented states/territories: NSW, WA, VIC, QLD, TAS, SA, ACT, NT
- High-sensitivity/summary-only sample count: 5
