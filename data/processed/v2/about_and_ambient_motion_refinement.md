# About And Ambient Motion Refinement

## Starting State

- Starting branch: `codex/map-flag-growth-refinement`
- Task branch: `codex/about-and-ambient-terminal-motion`
- Starting commit: `1419d0be31d97cb46424035603208ba69297e8bb`
- `origin/main`: `96383443a30d8b7558784d73ba730f538004148e`
- Localhost status: reused the existing repository dev server on `127.0.0.1:3000`
- Server PID: `73462`

No older GitHub version was restored. Existing unrelated data, collection, and document changes were left untouched.

## Source Ambient Elements

The `/source` structure and draggable split-pane behavior were preserved.

Ambient Anime.js loop targets:

- Header live status LED.
- Central divider live LED.
- Active source-family marker in the rollup.
- Two central divider tick marks.

Interaction animations already present for selected-source bracket draw-in, inspector separator draw-in, and filter result marker flash were preserved. Source names, numbers, rows, and disclaimer text are not animated.

## Map Ambient Elements

The `/map` structure, coordinates, projection, boundaries, map eligibility, and one-record-one-flag invariant were preserved.

Ambient Anime.js loop targets:

- One right-readout status LED.
- One map source-block indicator.
- Four source-tone legend SVG glyphs.

The existing bounded map flag growth animation remains page-load only. The ambient loop does not target `.record-flag-glyph` data markers. Final DOM QA showed:

- Rendered `[data-record-id]` markers: `1206`
- Unique marker record IDs: `1206`
- Visible map count uses `1206`, not `1,206`

## Anime.js Lifecycle Cleanup

- Source ambient motion remains scoped to the Source root element and cancels timelines on unmount.
- Map ambient motion is scoped to the Map root element and cancels/restarts safely on visibility changes.
- About ambient motion is scoped to `.about-view`, draws the data-flow line once, then loops only non-text status markers.
- All loops pause when `document.visibilityState !== "visible"` and resume when visible.
- Active timelines are cancelled on cleanup to avoid duplicate loops after Fast Refresh.

## Reduced Motion

- Source motion hook respects `prefers-reduced-motion`.
- Map ambient hook respects `prefers-reduced-motion`.
- About ambient hook respects `prefers-reduced-motion`.
- CSS keeps marker/line states visible and disables animated transforms under reduced motion.

The browser controller available in QA did not expose a reduced-motion media emulation switch. Reduced-motion screenshots are settled static equivalents, and the reduced-motion behavior was verified by code and CSS inspection.

## About Layout

`/about` was redesigned into a public research display terminal:

- Eyebrow: `ABOUT / PUBLIC DATA TERMINAL`
- Title: `AUSTRALIAN HUMANOID SUPERNATURAL TEXTS`
- Subtitle: `Public-text archive and research display system`
- Data status panel with public corpus metrics
- Research-positioning command strip
- Two-column module grid on desktop
- Scrollable lower modules
- Single-column mobile stack
- Lightweight SVG archive-model flow
- Terminal-style dotted leaders, status markers, raster cells, dividers, and framed modules

The page remains CSS/SVG/DOM only, with no images, canvas, video, or new asset dependencies.

## About Copy Changes

The About copy now explicitly positions the project as:

- a public-text archive;
- source-grounded;
- typed by narrative/source role;
- designed for research extension;
- not proof of supernatural claims;
- not an authoritative Indigenous knowledge repository;
- not a map of real-world supernatural distribution.

Prominent rule: `PUBLIC SOURCE EXISTS != SUPERNATURAL CLAIM VERIFIED`.

## Data-Driven Status Cells

Status cells derive from `public/data/frontend-data.json`:

- Public records: `3,809`
- Mapped records: `1,206`
- Source orgs: `49`
- Source types: `29`
- Date span: `1825-2026`

Record-type rows are also derived from frontend ontology counts. No crawler/query counts are used as public headline metrics.

## Desktop QA

- 1440 x 900 About top screenshot captured.
- 1440 x 900 About lower-module screenshot captured after internal scroll.
- About internal scroll verified: client height `754`, scroll height `1708`, post-scroll top `760`.
- About desktop had no horizontal overflow.
- Source default and selected-source screenshots captured.
- Source structure remained intact: split layout present, `7` rollup rows, `49` registry rows, `1` selected row.
- Map default and state-focus screenshots captured.
- Map DOM invariant held: `1206` rendered markers and `1206` unique marker IDs.
- Browser console QA reported no local app warnings or errors.
- Browser harness emitted external Statsig network timeouts unrelated to the local app.

## Mobile QA

- 390 x 844 About screenshot captured.
- About mobile had no horizontal overflow.
- About mobile status cells stack into a single column.
- Navigation links remain accessible.

## Navigation Check

About page navigation links:

- `/map`
- `/dashboard`
- `/density`
- `/source`

Existing Source/Map navigation was not redesigned.

## Screenshots

- `data/processed/v2/about_and_ambient_motion_screenshots/source_default_1440x900.png`
- `data/processed/v2/about_and_ambient_motion_screenshots/source_selected_source_1440x900.png`
- `data/processed/v2/about_and_ambient_motion_screenshots/source_reduced_motion_static_equivalent_1440x900.png`
- `data/processed/v2/about_and_ambient_motion_screenshots/map_default_ambient_1440x900.png`
- `data/processed/v2/about_and_ambient_motion_screenshots/map_state_focus_1440x900.png`
- `data/processed/v2/about_and_ambient_motion_screenshots/about_desktop_top_1440x900.png`
- `data/processed/v2/about_and_ambient_motion_screenshots/about_desktop_lower_1440x900.png`
- `data/processed/v2/about_and_ambient_motion_screenshots/about_mobile_390x844.png`
- `data/processed/v2/about_and_ambient_motion_screenshots/about_reduced_motion_static_equivalent_1440x900.png`

## Build Result

- `npm run typecheck`: passed.
- `npm run build`: passed.
- Post-build route checks passed for:
  - `/about`
  - `/source`
  - `/map`
  - `/dashboard`
  - `/density`

## Files Changed

- `app/about/page.tsx`
- `app/globals.css`
- `components/about/about-ambient-motion.tsx`
- `components/archive-terminal.tsx`
- `components/source/use-source-terminal-motion.ts`
- `data/processed/v2/about_and_ambient_motion_refinement.md`

## Remaining Limitations

- Reduced-motion browser screenshots are static settled equivalents because the available browser controller cannot emulate `prefers-reduced-motion`.
- The About page intentionally scrolls inside the terminal frame on desktop so the content can remain readable instead of being compressed into one viewport.
