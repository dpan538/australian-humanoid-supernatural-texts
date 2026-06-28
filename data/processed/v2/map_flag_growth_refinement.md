# Map Flag Growth Refinement

## Starting State

- Starting branch before task branch: `codex/source-terminal-refinement`
- Task branch: `codex/map-flag-growth-refinement`
- Starting commit: `41517b2c83457e8bc192cb26efaac22e5a82f9b2`
- `origin/main`: `96383443a30d8b7558784d73ba730f538004148e`
- Localhost: reused repository dev server on `127.0.0.1:3000`
- Server PID: `73462`

## Frontend-Derived Flag Count

- `summary.mapped_record_count`: `1206`
- `map_flags.length`: `1206`
- `map_points.length`: `1206`
- Rendered `[data-record-id]` markers: `1206`
- Unique rendered record IDs: `1206`
- Duplicate rendered record IDs: `0`

The count is derived from `public/data/frontend-data.json` and the rendered SVG DOM. No hard-coded `1206` value was added.

## Previous Large-Set Behavior

The previous map path used `largeFlagSet` when more than 800 flags were present. That disabled the marker arrival delay for the current 1206-record dataset, so the intended staggered entrance was effectively bypassed.

The `largeFlagSet` branch and per-index delay were removed.

## New Bounded Bucket Animation

- Added `useMapFlagGrowth` for map-specific Anime.js entrance choreography.
- The animation targets `.record-flag-glyph`, not the invisible hit circles or the whole SVG group.
- Flags start at opacity `0` and scale `0.16`, then settle at opacity `1` and scale `1`.
- Flags are divided into 12 west-to-east projected-X buckets.
- Bucket cadence is `64ms`.
- Per-bucket internal delay is capped to a repeating `0-15ms` pattern so dense buckets do not extend the full animation.
- Final settle keyframe runs at `1320ms`.
- Browser timing QA showed all `1206` glyphs settled by `1450ms`.
- The hook cancels an active timeline before starting another and cleans up on unmount.
- The data signature is `length:first flag_id:last flag_id`, so hover, focus, and record-overlay changes do not restart the full entrance.

## Marker Glyph Structure

Each public record marker remains one interactive SVG group:

- `.record-flag[data-record-id]`
- `.record-flag-hit` transparent hit circle
- `.record-flag-glyph[data-growth-bucket]`
- `.record-flag-under-ring`
- `.record-flag-ring`
- `.record-flag-core`

Resting markers use a small persistent core plus a faint source-tone ring and dark under-ring. Hover/focus/selected states enlarge and brighten the marker without hiding neighboring records.

## Collision Treatment

Exact projected coordinate collisions are handled in presentation only:

- One marker remains rendered per record.
- Exact `x/y` collision groups receive deterministic circular micro-offsets.
- Offset radius is capped at `4.4px`.
- A faint connector line points back to the true projected coordinate.
- Current rendered connector count: `816`.

No exported coordinates, database coordinates, map eligibility, or source-stated places were changed.

## Source-Tone Legend

Added a compact map-only source legend under the right readout:

- Repository / archive: `80`
- Public-domain text: `68`
- Modern public web: `903`
- Public institution: `155`

The legend uses the same marker glyph style as the map and does not expose raw enum strings. It is separate from the terrain legend.

## Map-Specific Number Formatting

Added `mapCount()` for the map page only.

- Main readout: `1206`
- Mapped-record summary: `1206`
- State mini counts: ungrouped integers
- Total note: `1206 mapped / 3809 public records`

Dashboard, Source, Density, and About number formatting were not changed.

## Readout Wording

- Replaced `POINT GEO` with `MAPPED RECORDS`.
- Main readout now reads `REGION / Australia / 1206 / mapped records`.
- Added the public note: `one flag per verified public record`.
- The wording avoids sightings, entities, populations, habitats, and supernatural truth claims.

## Reduced Motion

- `useMapFlagGrowth` checks `usePrefersReducedMotion()`.
- In reduced-motion mode, markers are immediately set to opacity `1` and scale `1`.
- CSS disables the active marker ring bloom under `prefers-reduced-motion: reduce`.
- The browser controller used for QA did not expose a reduced-motion media emulation switch, so the screenshot is a settled static equivalent. The code path and CSS media query were verified.

## Performance Observations

- Rendered marker groups: `1206`.
- Animated properties are limited to opacity and transform scale on glyph wrappers.
- No SVG filters, blur, path geometry, coordinates, terrain fills, or React layout properties are animated.
- No per-marker React callback closures were added; existing delegated marker event handling is preserved.

## QA Results

- `/map`: passed curl before edits and after build.
- `/dashboard`: passed curl before edits and after build.
- `/density`: passed curl before edits and after build.
- `/source`: passed curl before edits and after build.
- `/about`: passed curl before edits and after build.
- Typecheck: `npm run typecheck` passed.
- Build: `npm run build` passed.
- Browser console: no page `error` or `warn` logs during final map QA.
- Browser harness emitted external Statsig network timeout messages unrelated to the local app.
- 1440 x 900: `1206` rendered markers, no comma count, legend visible, selected marker label visible.
- 1280 x 800: `1206` rendered markers, no horizontal overflow, no comma count.
- 1024 x 768: `1206` rendered markers, no horizontal overflow, no comma count.
- 390 x 844: `1206` rendered markers, no horizontal overflow, right readout stacks below the map.
- State focus QA: NSW readout showed `499` and linked `499` markers; WA readout showed `38` and linked `38` markers.
- Active marker QA: clicking a marker opened the existing record overlay and kept one selected marker label visible.

## Screenshots

- Baseline: `data/processed/v2/map_flag_growth_screenshots/baseline_map_1440x900.png`
- Growth start: `data/processed/v2/map_flag_growth_screenshots/growth_start_1440x900.png`
- Growth halfway: `data/processed/v2/map_flag_growth_screenshots/growth_halfway_1440x900.png`
- Completed map: `data/processed/v2/map_flag_growth_screenshots/completed_full_australia_1440x900.png`
- NSW state focus: `data/processed/v2/map_flag_growth_screenshots/state_focus_nsw_1440x900.png`
- WA state focus: `data/processed/v2/map_flag_growth_screenshots/state_focus_wa_1440x900.png`
- Active marker and overlay: `data/processed/v2/map_flag_growth_screenshots/active_marker_selected_label_1440x900.png`
- Source-tone legend: `data/processed/v2/map_flag_growth_screenshots/source_tone_legend_1440x900.png`
- Reduced-motion static equivalent: `data/processed/v2/map_flag_growth_screenshots/reduced_motion_static_equivalent_1440x900.png`
- Mobile map: `data/processed/v2/map_flag_growth_screenshots/mobile_map_390x844.png`

## Files Changed

- `components/archive-terminal.tsx`
- `app/globals.css`
- `data/processed/v2/map_flag_growth_refinement.md`

## Remaining Limitations

- The in-app browser controller cannot directly emulate `prefers-reduced-motion`, so reduced-motion was verified by code/CSS inspection and a settled static screenshot rather than a true emulated media-mode screenshot.
- Some exact-coordinate collision groups are dense; the micro-offset keeps one marker per record visible without changing the underlying map coordinates, but very dense east-coast clusters remain intentionally compact.
