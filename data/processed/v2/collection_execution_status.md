# Collection Execution Status

- Generated: `2026-06-22`
- Starting checkpoint: `16a407da7d11ec4e531a31e89417a7fe82c30f9b`
- Implementation checkpoint commit: `e9845f2`

## Headline Counts

- Baseline canonical record count: `1097`
- Baseline mapped-record count: `832`
- Promoted staging candidates before new collection: `43`
- Post-promotion canonical record count: `1140`
- Net-new collected records: `60`
- Post-collection total: `1200`
- Post-collection mapped records: `832`
- Public map invariant: `mapped_record_count == map_points.length == map_flag_count == 832`

## Source Organisations Added

| source organisation | records |
|---|---:|
| Project Gutenberg Australia | 60 |

## Records By Jurisdiction

| jurisdiction | canonical public records |
|---|---:|
| NSW | 506 |
| QLD | 350 |
| unmapped | 126 |
| VIC | 97 |
| WA | 51 |
| NT | 27 |
| ACT | 17 |
| SA | 14 |
| TAS | 12 |

Records without a state/territory-level public map or corpus assignment remain valid display records when their source evidence is broad, book-level, or culturally sensitive.

## Records By Narrative Type

| narrative type | canonical public records |
|---|---:|
| cryptid_style_apeman | 1028 |
| traditional_narrative | 54 |
| spirit_being | 31 |
| ancestral_being | 28 |
| spirit_person_narrative | 24 |
| ghost_legend | 8 |
| giant_or_ogre_narrative | 7 |
| cautionary_being | 4 |
| giant | 4 |
| apparition_account | 3 |
| descriptive_belief_record | 2 |
| local_legend | 2 |
| retelling_or_adaptation | 2 |
| encounter_account | 1 |
| non_humanoid_control | 1 |
| satire | 1 |

## Failed Routes Skipped Or Stopped

- Trove article HTML, Trove OCR rendition guesses, NLA `.txt` guesses, and unauthenticated Trove API were skipped according to `source_route_failure_log.md`; `TROVE_API_KEY` was not used.
- Existing OpenAlex/Crossref query sets, broad Internet Archive ghost/Victorian searches, broad AYR expansion, generic whole-site institutional sitemap crawling, and tourism-only routes were not retried.
- Victorian Collections stopped immediately because automated public search pages returned Cloudflare challenge pages.
- eHeritage Tasmania stopped because the public search route returned an unavailable Azure app page.
- Territory Stories stopped after 30 reviewed candidates produced zero accepted records.
- Moreton Bay Our Story stopped because HTTPS/TLS failures prevented route inspection from this environment.

## Productive Routes

- `project_gutenberg_australia_exact_folklore`: 60 accepted records from exact public-domain full-text Australian folklore titles across two capped batches.

## Next Three Recommended Batches

1. Continue Project Gutenberg Australia exact-title extraction with additional Australian public-domain local-history and folklore books, capped at 30 reviewed story units per batch.
2. Use Territory Stories only with narrower exact-title or person-form queries and item handles, not broad `ghost` searches.
3. Revisit state-library or municipal digital collection item pages where full item text, stable identifiers, and source organisation metadata are exposed without authentication.
