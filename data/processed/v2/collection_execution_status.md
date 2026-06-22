# Collection Execution Status

- Generated: `2026-06-22`
- Starting checkpoint: `16a407da7d11ec4e531a31e89417a7fe82c30f9b`
- Implementation checkpoint commit: `e9845f2`

## Headline Counts

- Baseline canonical record count: `1097`
- Baseline mapped-record count: `832`
- Promoted staging candidates before new collection: `43`
- Post-promotion canonical record count: `1140`
- Net-new collected records: `90`
- Post-collection total: `1217`
- Post-collection mapped records: `832`
- Public map invariant: `mapped_record_count == map_points.length == map_flag_count == 832`

## Source Organisations Added

| source organisation | public-exported records |
|---|---:|
| Project Gutenberg Australia | 47 |
| Internet Sacred Text Archive | 20 |
| Wikisource | 10 |

PGA audit note: 60 canonical PGA records remain auditable; 13 are scope-suppressed from public export counts.

## Records By Jurisdiction

| jurisdiction | canonical public records |
|---|---:|
| NSW | 500 |
| QLD | 350 |
| unmapped | 122 |
| VIC | 102 |
| WA | 51 |
| NT | 47 |
| ACT | 17 |
| SA | 16 |
| TAS | 12 |

Records without a state/territory-level public map or corpus assignment remain valid display records when their source evidence is broad, book-level, or culturally sensitive.

## Records By Narrative Type

| narrative type | canonical public records |
|---|---:|
| cryptid_style_apeman | 1028 |
| spirit_person_narrative | 58 |
| traditional_narrative | 35 |
| spirit_being | 31 |
| ancestral_being | 28 |
| ghost_legend | 8 |
| apparition_account | 5 |
| giant_or_ogre_narrative | 5 |
| descriptive_belief_record | 4 |
| cautionary_being | 4 |
| giant | 4 |
| retelling_or_adaptation | 2 |
| local_legend | 2 |
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

- `project_gutenberg_australia_exact_folklore`: 60 accepted records from exact public-domain full-text Australian folklore titles across two capped batches; 13 are now scope-suppressed after audit.
- `internet_sacred_texts_exact_ethnography`: 20 accepted records from exact public-domain Australian ethnographic chapters.
- `wikisource_australian_ethnography_exact_text`: 10 accepted records from exact public-domain south-east Australian ethnographic chapters.

## Next Three Recommended Batches

1. Prioritize municipal/state library item pages and local-history PDFs in VIC, WA, SA, TAS, NT, and ACT with stable public identifiers.
2. Use Territory Stories only with narrower exact-title or person-form queries and item handles, not broad `ghost` searches.
3. Continue exact public-domain non-PGA chapters only where named supernatural/person-form evidence is explicit and culturally appropriate for public summary display.
