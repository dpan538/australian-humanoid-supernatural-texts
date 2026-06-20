# Internet Archive Strict-Geo Audit

- Generated: `2026-06-20`
- Batch runs: `v2_collection_ia_strict_001`, `v2_collection_ia_strict_002`
- Strict geography mode: `true`

## Outcome

- New accepted strict-geo source items from Internet Archive in these runs: `0`
- Existing cumulative accepted V2 source items: `1`
- New IA candidates staged across the two runs: leads/rejections/duplicates only

## Main Rejection And Lead Reasons

- Public OCR/text unavailable for many relevant-looking items.
- Some candidate texts were accessible but did not include a strict project gazetteer place.
- Several text/metadata requests failed with TLS/SSL connection errors in the current network environment.
- High-sensitivity traditional/spirit-person materials are kept as leads unless human ethics review promotes them.
- Metadata-only records and source pointers remain non-countable.

## Trove Check

Known NLA/Trove article IDs were tested against the public rendition route. The request returned a site-protection HTML response rather than article OCR text. The collector must not bypass this protection. Trove remains a lead/manual-import/API-key route unless article-level text is supplied through an allowed channel.

## Engineering Consequence

Internet Archive can remain a supporting collector for public-domain books and archival items, but it is not a scalable source for the next `+500` to `+1000` strict-geocoded accepted records. The next productive route should prioritize:

- manually verified Trove article imports with stable article IDs and OCR/text;
- public institutional pages with named sites;
- reputable media/local-history pages with exact place evidence;
- community-controlled public pages only where display and reuse are clearly appropriate.
