# Map Marker Bug Fix Report

- Starting branch: `codex/map-dot-bug-fix`
- Starting commit: `14e81cc0a9b84f6c71268d75d84a11f7d497e905`
- Localhost status: existing Next.js dev server on `127.0.0.1:3000`
- Server PID: `73462`

## Marker Count

- `mapped_record_count`: `1206`
- `map_flags.length`: `1206`
- `map_points.length`: `1206`
- Rendered marker groups in `/map`: `1206`
- Rendered visible marker dots in `/map`: `1206`

The marker count invariant is preserved.

## Rendering Change

Markers were changed to simple, solid source-family colour dots.

- Default marker radius: `3.6px`
- State-linked marker radius: `3.8px`
- Hover/active marker radius: `5.2px`
- Normal marker stroke: removed
- Normal marker connector lines: removed from rendering
- Normal marker glow/filter/halo: none

The previous black-outline appearance came from `.record-flag-dot` using `stroke: rgba(0, 0, 0, 0.68)` and `stroke-width: 0.58`. Signal-gain and contrast overrides also reintroduced dark strokes. Those strokes are now removed.

## Chronological Reveal

The marker growth animation still uses Anime.js and runs once when map data loads.

The reveal is now chronological rather than geographic. Each mapped marker uses its mapped record `year` when available and falls back to the record date band when needed.

Chronological batches:

- pre-1842
- 1842-1875
- 1876-1900
- 1901-1950
- 1951-1969
- 1970-1990
- 1991-2010
- 2011-present

Observed DOM bucket counts after loading:

- `0`: `1`
- `1`: `42`
- `2`: `106`
- `3`: `99`
- `4`: `14`
- `5`: `223`
- `6`: `324`
- `7`: `397`

Animation timing is bounded: each wave is about `320ms`, wave starts are spaced by `150ms`, and the full reveal resolves at about `1.52s`.

## Collision Bug Diagnosis

The six-dot flower/ring bug was caused by the collision layout in `prepareMapFlagPresentation`. Records sharing identical projected coordinates were sorted and placed around a center using:

- a radial angle;
- a group radius;
- evenly spaced positions around a full circle;
- connector lines from the original point to the displayed point.

That produced rosettes and hexagonal/flower patterns that looked like meaningful geometry.

## Collision Fix Applied

The radial spread was replaced with deterministic micro-jitter.

- No visible radial pattern.
- No symmetric circle/flower/hexagon layout.
- No connector lines.
- Stable across sessions.
- Deterministic from record id and collision index.
- Maximum offset is about `2.1px` horizontally and `1.9px` vertically.

The dense areas now read as dense point areas rather than decorative clusters.

## Performance Observations

- No continuous animation on all markers.
- No SVG blur or glow filters on marker dots.
- No permanent halo layers.
- No connector-line rendering for collision groups.
- Marker event delegation remains on the parent flag layer.
- Marker DOM remains one hit circle plus one visible dot, with an active-only ring and label.

## QA

- No black-outline appearance in computed marker styles.
- Normal marker computed style: `stroke: none`, `stroke-width: 0px`.
- Active marker computed style: `r: 5.2`, `stroke: none`, `stroke-width: 0px`.
- Console warnings/errors after map load: none.
- Hydration warnings observed: none.
- `/map` route curl result: pass.
- Build result: pass.

## Screenshot Paths

- Current broken outlined markers: `data/processed/v2/map_marker_bugfix_screenshots/01_current_broken_outlined_markers.png`
- Fixed chronological reveal in progress: `data/processed/v2/map_marker_bugfix_screenshots/02_fixed_chronological_reveal_in_progress.png`
- Fixed finished solid dots: `data/processed/v2/map_marker_bugfix_screenshots/03_fixed_finished_solid_dots.png`
- Fixed dense east-coast region: `data/processed/v2/map_marker_bugfix_screenshots/04_fixed_dense_east_coast_region.png`
- Fixed overlap case with no rosette: `data/processed/v2/map_marker_bugfix_screenshots/05_fixed_overlap_no_rosette.png`
- Fixed active marker state: `data/processed/v2/map_marker_bugfix_screenshots/06_fixed_active_marker_state.png`

