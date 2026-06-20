# Confidence, Dashboard, and Violation Audit

- Generated: `2026-06-20`
- Scope: current V2 database, frontend export, dashboard display contract, and strict-geography collection path.

## Current Corpus Confidence Layers

The current corpus should be read as layered, not as one flat confidence class.

| Layer | Count | Meaning | Frontend treatment |
| --- | ---: | --- | --- |
| Legacy/card-ready records | 985 | Records with enough fields for the overlay card and review display. | Can appear in record lists, dashboard density, source counts, and review workflows. |
| Migrated source items | 985 | Legacy records mapped into V2 `source_items`. | Normalized archive backbone. |
| Migrated narrative units | 916 | Distinct or provisionally distinct narrative units. | Analytical layer; still reviewable. |
| Strict geocoded frontend points | 1 | Records with verified latitude/longitude suitable for map flags. | Only these should render as individual map points. |
| Broad/non-strict location signals | 114 | State/region/locality text that is not yet strict map-grade. | Review/export only; not individual map flags. |
| Strict collection candidates accepted | 1 | New strict-geography candidate accepted by V2 gate. | Collection target progress. |
| Strict collection leads | 18 | Search/source leads, not accepted records. | Do not count toward collection target. |

## Confidence Interpretation

- `display_ready_unreviewed` or card-ready means the item is usable for review and visual display, not that the source interpretation is final.
- `strict geocoded` means the public item has a verified coordinate tied to a named place or feature. It does not verify supernatural claims.
- `lead_only` means the item may be useful for future collection but lacks article-level evidence, stable source text, verified coordinates, or another required field.
- `caution_indigenous_knowledge` means the record requires careful source/community terminology, publicness review, and conservative display mode. Public discoverability is not permission for unrestricted reproduction.

## Dashboard Chart Plan Assessment

The dashboard should remain visually dense, but its internal modes must not collapse distinct confidence layers.

### Records Mode

Purpose: show the card-ready/public narrative corpus.

Recommended signals:

- `CARD READY`: total card-ready records.
- `FIGURES`: distinct figure/source-label groups.
- figure signal list: top source labels or canonical guesses.
- source wheel: legacy/source-family record mix.
- lollipops: all card-ready state/territory signals, clearly understood as narrative/source geography rather than verified event distribution.

### Geo Field Mode

Purpose: show strict map-grade data health.

Recommended signals:

- `STRICT`: verified geocoded map points.
- `BROAD`: broad or non-strict location signals that need review.
- state lollipops: strict geocoded counts only.
- effect grid: strict point counts by state/territory only.

This mode should stay visually sparse until the strict-geography collection grows. Sparse display is correct and preferable to artificial point placement.

### Query Field Mode

Purpose: show collection infrastructure and search pressure.

Recommended signals:

- `QUERIES`: planned query rows.
- `EXACT`: exact phrase query count.
- query type strips: exact, constrained, negative-control, attention-series, and fuzzy variants.
- source meters: query distribution by source family.

## Potential Violations Found

1. **Dashboard location ambiguity**
   - Problem: dashboard location mode used broad state counts while the top metric displayed strict point count.
   - Risk: user could infer that 985 records are all map-grade.
   - Status: fixed. `GEO FIELD` now uses strict geocoded state counts.

2. **Dashboard label ambiguity**
   - Problem: `PUBLIC` and `LOCATIONS` were too broad.
   - Risk: unclear whether the numbers mean public records, verified locations, or regional signals.
   - Status: fixed. Labels now distinguish `CARD READY`, `GEO FIELD`, `STRICT`, and `BROAD`.

3. **Audit report stale wording**
   - Problem: frontend audit referred to individual record flags in a way that implied every frontend record should map.
   - Risk: false failure interpretation after strict-map policy.
   - Status: fixed. Audit now states only verified latitude/longitude records should map as individual flags.

4. **Source and geography imbalance**
   - Problem: current record mix is heavily modern web / AYR-derived and Yowie-dominant.
   - Risk: visual density may look like distributional truth rather than source availability.
   - Status: not fixed by UI alone. Requires next collection batches with source diversification and strict geography gates.

5. **Metadata-only records in legacy display layer**
   - Problem: some legacy records come from academic or Internet Archive metadata and may be better represented as pointers or secondary discourse.
   - Risk: dashboard source wheel may overstate substantive narrative evidence.
   - Status: requires V2 reclassification review; not a frontend-only fix.

## Fixes Applied In This Pass

- Dashboard `LOCATIONS` tab renamed to `GEO FIELD`.
- `GEO FIELD` active values and lollipops now use strict geocoded map points, not broad state counts.
- Dashboard top metrics now show `STRICT` and `BROAD` for geography mode.
- Records mode now uses `CARD READY` instead of vague `PUBLIC`.
- Output-switch buttons now have descriptive labels for card-ready records, strict geocoded points, and planned queries.
- Frontend audit wording now matches strict-map policy.

## Next Execution Plan

1. **Create source-specific strict geocoding queues**
   - Prioritise Parks Victoria, Port Arthur, Fremantle Prison, state libraries, heritage registers, national parks, councils, and Trove article pages with named places.
   - Each queue row must include source URL, title, source tier, source label, location text, coordinate evidence, and quality class.

2. **Build batch imports in groups of 25-50**
   - Use `data/interim/strict_geo_manual_seed_candidates.csv` as the shape.
   - Import with `scripts/collect_v2_batch.py --strict-geo-only --target 3000`.

3. **Audit after each batch**
   - Run `make validate-v2`.
   - Run `make test`.
   - Run `make export-frontend`.
   - Inspect map point count, source mix, state/territory spread, and ethics flags.

4. **Do not count weak geography**
   - Country-only, state-only, broad-region, and publication-location-only records remain leads/review items.
   - They can improve narrative analysis but do not count toward the 3,000 strict-geography target.

5. **Frontend after data growth**
   - Once strict points exceed roughly 250, implement point-collision handling that preserves exact coordinate anchoring through small visual offsets or focus halos.
   - Keep the stored coordinate unchanged and expose it in the card/audit data.

