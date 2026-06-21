# Population Coverage Audit

- Generated: `2026-06-21T12:31:39+00:00`
- Frontend data record count: `1119`
- Strict map point count: `930`
- Population source: Australian Bureau of Statistics — National, state and territory population, December 2025
- Population table: `310104.xlsx, Table 4. Estimated Resident Population, States and Territories (Number)`
- Reference date: `2025-12-01`
- Source URL: https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population/dec-2025

## Interpretation Guardrail

This audit measures public-record coverage against population distribution. It does not measure the prevalence of supernatural claims, traditions, beings, sightings, or beliefs.

## Summary

- Display records assigned to a state/territory: `1047`
- Strict map points assigned to a state/territory: `928`
- Additional display records needed for every state/territory to reach 100: `384`
- Additional strict map points needed for every state/territory to reach 100: `456`
- Additional display records needed to approach a 3,500-record population-proportional target: `2453`
- Additional strict map points needed to approach a 1,500-point population-proportional target: `586`

## State/Territory Coverage

| State | Population | Display | Strict map | Display / 1m | Strict / 1m | Gap to 100 display | Gap to 100 strict | 3,500 display proportional target | Gap | 1,500 strict proportional target | Gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| WA | 3076528 | 51 | 15 | 16.58 | 4.88 | 49 | 85 | 387 | 336 | 166 | 151 |
| NT | 267478 | 27 | 17 | 100.94 | 63.56 | 73 | 83 | 34 | 7 | 14 | 0 |
| SA | 1910553 | 14 | 10 | 7.33 | 5.23 | 86 | 90 | 241 | 227 | 103 | 93 |
| QLD | 5712124 | 349 | 321 | 61.1 | 56.2 | 0 | 0 | 719 | 370 | 308 | 0 |
| NSW | 8641085 | 482 | 463 | 55.78 | 53.58 | 0 | 0 | 1088 | 606 | 466 | 3 |
| VIC | 7121913 | 96 | 82 | 13.48 | 11.51 | 4 | 18 | 897 | 801 | 384 | 302 |
| TAS | 579110 | 11 | 10 | 18.99 | 17.27 | 89 | 90 | 73 | 62 | 31 | 21 |
| ACT | 487202 | 17 | 10 | 34.89 | 20.53 | 83 | 90 | 61 | 44 | 26 | 16 |

## Collection Implication

- WA, NT, SA, TAS, ACT, and VIC remain the priority states for strict geocoded collection.
- NSW and QLD are already overrepresented relative to the current corpus and should receive only high-quality non-duplicative additions in the next collection pass.
- Broad or unresolved geography can still support dashboard and density views, but it should not be counted as a strict map point.
