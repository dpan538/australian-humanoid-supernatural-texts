# Dashboard Right Panel Refinement

## Local starting state

- Starting branch: `codex/frontend-optimization`
- Working branch created for this task: `codex/dashboard-right-panel-refinement`
- Starting `HEAD`: `96383443a30d8b7558784d73ba730f538004148e`
- Starting `origin/main`: `96383443a30d8b7558784d73ba730f538004148e`
- Initial status included many unrelated collection/data changes. No dashboard source file checkpoint commit was needed before edits because the only dirty frontend-derived tracked file was `public/data/frontend-data.json`, which was not modified or staged for this task.

## Localhost status

- Port 3000 was initially not listening.
- Dev server was started and left running at `http://127.0.0.1:3000/dashboard`.
- Listener after build: `node` PID `27844`.
- Final route checks passed for:
  - `http://127.0.0.1:3000/dashboard`
  - `http://127.0.0.1:3000/map`
  - `http://127.0.0.1:3000/density`
  - `http://127.0.0.1:3000/source`
  - `http://127.0.0.1:3000/about`

## Files changed

- `components/archive-terminal.tsx`
- `app/globals.css`
- `data/processed/v2/dashboard_right_panel_refinement.md`
- `data/processed/v2/dashboard_right_panel_screenshots/*.png`

No database, collection, canonical data, collector, SQLite, map, density, source, or about route files were changed.

## Field-view structures

### RECORDS

- Renders a distinct records field component.
- Expanded view contains:
  - compact layered record timeline;
  - narrative-by-period bubble matrix;
  - selected-period detail module with records, mapped share, source diversity, top narrative families, and representative records.
- Balanced view contains only a compact timeline preview plus two metrics.

### GEO FIELD

- Renders a distinct geographic field component.
- Expanded view contains:
  - state/territory paired lollipop bars;
  - location precision dot ladder;
  - place-role period heatmap;
  - narrative-geography disclaimer.
- Balanced view contains compact state coverage plus mapped-share metrics.

### SOURCE FIELD

- Renders a distinct source mediation component.
- Expanded view contains:
  - normalized source-period stacked ribbon;
  - large source-family donut;
  - ranked source-family bars with six-period mini-profiles.
- Balanced view contains a mini source ribbon plus compact donut.

## Flat-line replacement

The previous weak source line/infographic reuse was replaced by `SOURCE COMPOSITION THROUGH TIME`, a normalized stacked source-family ribbon over the six dated time-cutter periods. The normalization is labelled in the module subtitle.

## Time cutter

- Uses the six dated periods.
- Each segment now shows:
  - segment number;
  - date label;
  - record count.
- Typography was increased to approximately:
  - number: `11px`;
  - period: `11.5px`;
  - count: `10px`.
- Selected/hover state now uses a restrained amber accent and readable dark-panel contrast.

## Timeline size

- The records timeline is now a compact first-row module instead of a large full-panel chart.
- Expanded record timeline module height is reserved around the 220-270px target range.
- Balanced mode keeps only a preview-scale timeline.

## Source donut

- Expanded source donut uses a responsive 200-230px diameter.
- Legend uses full public source-family names with count and percentage.
- Labels are complete, though long names wrap on narrower expanded widths.

## Source bars

- The former plain horizontal strips were replaced with ranked source-family rows.
- Each row includes source family, count, share, thin proportional bar, and six-cell mini-profile.
- Row typography is reduced to the requested compact scale.

## Overlap prevention

- Right-panel modules use normal document flow.
- The right scroll body uses `overflow-y: auto`, `overflow-x: hidden`, and `scrollbar-gutter: stable`.
- Chart modules are independently boxed with `position: relative`, `min-width: 0`, and `overflow: hidden`.
- Two-column rows use CSS grid with `minmax(0, ...)` tracks and stack at narrower widths.
- No negative margins or shared absolute-positioned chart canvases were added.

## Anime.js field transitions

- Existing panel expansion animation was preserved.
- Added field-switch reveal choreography with cancellation:
  - RECORDS: bars/line draw, then matrix bubbles reveal.
  - GEO: lollipops rise, precision dots and heat cells reveal.
  - SOURCE: ribbon segments grow, then donut and ranked rows reveal.
- Empty animation target lists are skipped to avoid console warnings.
- `prefers-reduced-motion` is respected.

## Responsive results

- 1440 x 900: expanded two-column charts remain side by side; source donut is large; no chart overlap observed.
- 1280 x 800: not separately screenshotted, but same grid constraints apply below desktop width.
- 1024 x 768: two-column modules stack where needed through the `max-width: 1040px` rules.
- 390 x 844: right views are one column; time cutter wraps into a readable two-column grid; no horizontal body overflow was detected.

## Screenshots

- Baseline: `data/processed/v2/dashboard_right_panel_screenshots/baseline_dashboard_1440x900.png`
- Balanced RECORDS: `data/processed/v2/dashboard_right_panel_screenshots/balanced_records_1440x900.png`
- Balanced GEO FIELD: `data/processed/v2/dashboard_right_panel_screenshots/balanced_geo_1440x900.png`
- Balanced SOURCE FIELD: `data/processed/v2/dashboard_right_panel_screenshots/balanced_source_1440x900.png`
- Right-expanded RECORDS: `data/processed/v2/dashboard_right_panel_screenshots/right_expanded_records_1440x900.png`
- Right-expanded GEO FIELD: `data/processed/v2/dashboard_right_panel_screenshots/right_expanded_geo_1440x900.png`
- Right-expanded SOURCE top: `data/processed/v2/dashboard_right_panel_screenshots/right_expanded_source_top_1440x900.png`
- Right-expanded SOURCE donut/bars: `data/processed/v2/dashboard_right_panel_screenshots/right_expanded_source_donut_bars_1440x900.png`
- Right-expanded scrolled: `data/processed/v2/dashboard_right_panel_screenshots/right_expanded_scrolled_1440x900.png`
- Mobile RECORDS: `data/processed/v2/dashboard_right_panel_screenshots/mobile_records_390x844.png`
- Mobile SOURCE FIELD: `data/processed/v2/dashboard_right_panel_screenshots/mobile_source_390x844.png`

## Build result

- `npm run typecheck`: passed.
- `npm run build`: passed.
- Browser console on fresh QA tab: no app errors or warnings.

## Remaining limitations

- The source donut legend keeps full names, so very long source-family labels wrap in expanded mode instead of truncating.
- The dashboard continues to use the currently running local frontend data cache/counts; this task did not regenerate or modify canonical frontend data.
