# Public Collection Round 001

Run name: `public_round_001`
Records inserted or updated: 13
Source leads written: 32
Fetch failures logged: 0
Earliest year in imported/lead records: 1842
Record-location links written: 24

## Method

- Small, public-only collection round.
- Wikimedia summaries were retrieved through public API endpoints.
- ABC News Kilcoy page was downloaded as a public web page.
- Trove/NLA early items were inserted as public metadata leads only because Trove API requires a key and full article pages were not reliably retrievable from this environment.
- No restricted, secret/sacred, unpublished, or non-public materials were targeted.

## Imported Records

-  | English Wikipedia | Quinkan | figure=Quinkan | ethics=caution_indigenous_knowledge
- 1842 | Manual Import | Superstitions of the Australian Aborigines: The Yahoo | figure=Yahoo | ethics=ok_public
- 1876 | Trove Newspapers and Gazettes | Milburn Creek | figure=Yahoo | ethics=ok_public
- 1882 | Trove Newspapers and Gazettes | The Naturalist: Australian Apes | figure=Yowie | ethics=ok_public
- 1976 | Trove Newspapers and Gazettes | Home-made 'Yowie' | figure=Yowie | ethics=ok_public
- 1976 | Trove Magazines and Newsletters | It's huge, hairy and from Cape York to Tasmania the monster Yowie prowls | figure=Yowie | ethics=ok_public
- 2018 | ABC News | Yowie country: Queensland town revamps tourism brand as a prime spot for mythological creature | figure=Yowie | ethics=ok_public
- 2026 | English Wikipedia | Yowie | figure=Yowie | ethics=ok_public
- 2026 | English Wikipedia | Yara-ma-yha-who | figure=Yara-ma-yha-who | ethics=caution_indigenous_knowledge
- 2026 | English Wikipedia | Wandjina | figure=Wandjina | ethics=caution_indigenous_knowledge
- 2026 | English Wikipedia | Bunyip | figure=Bunyip | ethics=caution_indigenous_knowledge
- 2026 | English Wikipedia | Drop bear | figure=Drop bear | ethics=ok_public
- 2026 | English Wikipedia | Nargun | figure=Nargun | ethics=caution_indigenous_knowledge

## Fetch Failures

- None

## Output Files

- `data/interim/public_round_001_records.csv`
- `data/interim/public_round_001_source_leads.csv`
- `data/exports/records_review.csv` after running `make locations export`
- `data/exports/record_locations.csv` after running `make locations export`
