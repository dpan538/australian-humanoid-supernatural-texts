# Public Round Lead Coverage Audit

Created at: `2026-06-19T10:53:34+00:00`
Round: `public_round_002`
Planned public leads audited: 264

This audit covers planned leads only. Leads are not records and must not be counted as frontend record cards until source-item metadata is verified.
- NOTE: Planned lead coverage is not balanced: modern material dominates and the 1803-1841 backsearch window is thin.
- NOTE: Most planned leads require article-specific location extraction before map placement.
- NOTE: Planned state/territory hints are missing: NSW, SA, TAS, ACT.

## Planned Date Band Coverage

- `modern_yowie_heritage_tourism_media`: 144 (54.5%)
- `early_anchor`: 48 (18.2%)
- `publication_expansion`: 48 (18.2%)
- `backsearch_negative_control`: 24 (9.1%)

## Planned Location Hint Coverage

- `article_specific_au`: 154 (58.3%)
- `NT`: 44 (16.7%)
- `QLD`: 22 (8.3%)
- `WA`: 22 (8.3%)
- `VIC`: 11 (4.2%)
- `source_required`: 11 (4.2%)

## Planned Source-Type Coverage

- `trove_newspaper`: 96 (36.4%)
- `trove_magazine`: 72 (27.3%)
- `aiatsis_public_catalogue`: 24 (9.1%)
- `andc`: 24 (9.1%)
- `modern_web`: 24 (9.1%)
- `nla_catalogue`: 24 (9.1%)

## Planned Figure Coverage

- `Yowie`: 33 (12.5%)
- `Hairy Man`: 22 (8.3%)
- `Mimih`: 22 (8.3%)
- `Quinkan`: 22 (8.3%)
- `Wandjina`: 22 (8.3%)
- `Yahoo`: 22 (8.3%)
- `Yara-ma-yha-who`: 22 (8.3%)
- `Bunyip`: 11 (4.2%)
- `Drop bear`: 11 (4.2%)
- `Garkain`: 11 (4.2%)
- `Mamu`: 11 (4.2%)
- `Mokoi`: 11 (4.2%)
- `Nargun`: 11 (4.2%)
- `Pangkarlangu`: 11 (4.2%)
- `Puttikan`: 11 (4.2%)
- `Yaroma`: 11 (4.2%)

## Planned Execution Priority

- `5`: 141 (53.4%)
- `4`: 77 (29.2%)
- `3`: 34 (12.9%)
- `2`: 12 (4.5%)

## Planned High-Noise Guard

- `ok`: 220 (83.3%)
- `MANUAL_REVIEW_RECOMMENDED`: 44 (16.7%)

## Next Round 500 Plan

- Do not count query-level leads as records or frontend record cards.
- A new record must have enough card fields: date/year or date note, title or figure label, source, URL/external id, snippet/description, publicness, and location evidence.
- Use source-specific collectors or manual exports for concrete items, starting with Trove/NLA where article-level metadata can be verified.
- Suggested date quotas for the next 500 true records: 160 backsearch 1803-1841, 130 early anchor 1842-1875, 130 publication expansion 1876-1969, 80 modern 1970-present.
- Suggested region work: resolve article-specific AU leads into states first, then prioritise NSW, SA, TAS, ACT, and VIC until each has visible map/card presence.
- Validation-queue terms remain leads only until manually promoted after public-source and ethics review.
