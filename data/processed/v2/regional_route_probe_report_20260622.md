# Regional Route Probe Report

- Generated: `2026-06-22`
- Probe limit: 30 reviewed candidates per productive route
- Collection standard: accepted records require substantive public narrative evidence, stable public URL or identifier, publicness/rights note, duplicate check, and neutral summary.

| route_id | source organisation | retrieval method | candidates processed | accepted | duplicates | leads | rejected | acceptance rate | runtime | stop reason | next action |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| victorian_collections_probe_001 | Victorian Collections | public item/story search URL probe | 0 | 0 | 0 | 0 | 0 | 0.000 | ~6s | Automated requests returned Cloudflare challenge pages. | Do not retry automated route unless a documented API/export route is supplied. |
| eheritage_tasmania_probe_001 | Libraries Tasmania eHeritage | public search URL probe | 0 | 0 | 0 | 0 | 0 | 0.000 | ~6s | Public search redirected to unavailable Azure app page. | Retry only if site availability changes or item URLs are supplied manually. |
| territory_stories_lant_probe_001 | Library & Archives NT / Territory Stories | documented public `/api/search` POST after inspecting search bundle | 30 | 0 | 0 | 30 | 0 | 0.000 | 3.2s | Thirty reviewed `ghost` candidates produced zero accepted records; results were dominated by non-narrative false positives such as ghost nets or bare newspaper issue hits. | Use narrower exact-title/person-form queries or supplied item handles; do not continue broad `ghost` route. |
| moreton_bay_our_story_probe_001 | Moreton Bay Our Story | homepage and search URL probe | 4 | 0 | 0 | 0 | 4 | 0.000 | ~2s | HTTPS/TLS failures prevented route inspection from this environment. | Retry only after site access is verified in a browser or alternate public endpoint is documented. |
| project_gutenberg_australia_exact_folklore | Project Gutenberg Australia | catalogue-to-exact-title full-text HTML extraction | 30 | 30 | 0 | 0 | 0 | 1.000 | 6.5s probe; 0.1s import | First 30 reviewed story units accepted; route remained within exact-title public-domain book scope. | Continue exact Australian folklore/local-history titles; avoid broad global ghost searches. |

## Batch Summary

- Productive route selected: `project_gutenberg_australia_exact_folklore`.
- Source items used: `Australian Legends`, `Australian Legendary Tales`, and `More Australian Legendary Tales`.
- Net-new accepted canonical records: `30`.
- Map impact: `0` new map flags; all batch locations are broad book/cultural-region associations and are intentionally excluded from the public map subset.
