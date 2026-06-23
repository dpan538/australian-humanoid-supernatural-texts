# Source Terminal Refinement

## Starting State

- Working directory: `/Users/jarlgiovanni/Desktop/bigfoot_research`
- Starting commit: `6740f9ce395fc9fac0254ecf5d313cfdca01c897`
- Starting branch before this task: `codex/dashboard-right-panel-refinement`
- Working branch: `codex/source-terminal-refinement`
- `origin/main`: `96383443a30d8b7558784d73ba730f538004148e`
- Localhost status: existing repository dev server reused on PID `27844`, listening on `127.0.0.1:3000`

## Count Reconciliation

Current frontend export counts were rechecked from `public/data/frontend-data.json`:

- Public records: `3,809`
- Map flags: `1,206`
- Map points: `1,206`
- Mapped unique records: `1,206`
- Source organisations: `49`
- Source types represented in public frontend data: `29`

The frontend data loader now uses `cache: "no-store"` so dashboard views and Source details re-read the current local export instead of retaining stale browser/framework cached counts.

## Files Changed

- `components/archive-terminal.tsx`
  - Source view moved to Source-specific component.
  - Data request changed from `force-cache` to `no-store`.
  - Source dock duplicate-label regression fixed so `/source` shows `About`, `Source`, `Dashboard`.
- `components/source/source-view.tsx`
  - New two-pane Source terminal view.
  - Header metrics, rollup pane, registry pane, filter, selected source inspector.
- `components/source/use-source-pane-resize.ts`
  - Pointer Events splitter with keyboard controls, reset, ratio persistence, and drag-safe CSS variable updates.
- `components/source/use-source-terminal-motion.ts`
  - Subtle Anime.js non-text breathing/selection/filter effects with reduced-motion and visibility cleanup.
- `lib/source-view-data.ts`
  - Frontend-only memoized Source page aggregations and human-readable label mappings.
- `app/globals.css`
  - Source terminal split layout, scroll containers, divider, rows, filter, inspector, responsive rules, and refined header metric block.
- `data/processed/v2/source_terminal_refinement.md`
  - This report.

## Split Pane

- Default left pane ratio: `38%`
- Minimum left ratio: `28%`
- Maximum left ratio: `58%`
- Normal desktop right pane minimum: approximately `420px`
- Dragging uses Pointer Events and requestAnimationFrame-driven CSS variable updates.
- Divider release persists the ratio in `localStorage`.
- Double-click resets to `38%`.
- Keyboard controls:
  - Left / Right Arrow: `2%`
  - Shift + Arrow: `8%`
  - Home: minimum
  - End: maximum
  - Enter / Space: reset
- The divider exposes `role="separator"`, vertical orientation, min/max/current values, and focus styling.

## Scroll Behavior

- Registry pane scrolls independently with `overflow-y: auto`, `overflow-x: hidden`, `scrollbar-gutter: stable`, and `overscroll-behavior: contain`.
- Rollup pane uses the same independent scroll container pattern.
- The rollup pane now includes a compact public source-type signal section below source-family aggregates, so the left pane has useful scrollable content without adding fake rows.

## Terminal Visual Language

- The Source page keeps `SOURCE REGISTER`, `PUBLIC SOURCE FIELD`, the dark archive terminal palette, cyan accents, monospaced typography, outer frame, and public-source disclaimer.
- The header metric area was redesigned after visual QA:
  - Replaced surprising pale floating blocks with a dark aligned terminal status strip.
  - Added visible values directly under labels.
  - Increased upper-right status label/value type by about 10%.
  - Verified computed sizes: labels `12.8px`, values `17.6px`.
- Rollup rows use human-readable family labels, dotted leaders, compact numeric columns, and small source-family markers.
- A secondary `TYPE SIGNAL` rollup lists the top public display types derived from the same registry aggregates.
- Registry rows use aligned columns for source organisation, public role, records, and type.

## Human-Readable Labels

Raw source type values are mapped to public labels such as:

- `repository_full_text` -> `Full text`
- `public_domain_ebook` -> `Public-domain book`
- `project_gutenberg_australia_book` -> `Public-domain book`
- `institutional_web` -> `Institutional web`
- `academic_metadata` -> `Academic metadata`

Source-family labels include:

- Repository texts
- Modern public web
- Public-domain books
- Public institutions
- Academic / catalogue sources
- Community-controlled public sources
- Other public sources

## Source Inspector

Selecting or focusing a registered source updates a compact inspector at the bottom of the registry pane. It displays available public frontend fields:

- Full organisation name
- Public source role
- Source family
- Public record count
- Date span
- Narrative labels
- Jurisdictions
- Source URL when available
- Publicness value

Example QA selection: `Project Gutenberg` showed `499` public records, `1872-1924`, represented narratives, jurisdictions, URL, and publicness.

## Filter Behavior

- Filter line uses normal text input semantics.
- `/` focuses the filter when no editable control is active.
- Escape clears the filter when focused.
- Filtering searches organisation, source family, role/display type, publicness, and raw source type.
- QA filter example: `gutenberg` returned `3 shown`.

## Anime.js

Breathing effects are limited to non-text elements:

- Header status LED
- Divider live LED
- Active source-family marker

Interaction effects:

- Selected-source bracket draws in.
- Inspector separator line draws in.
- Filter result marker flashes once.

Reduced motion disables the loops and scale pulses through `prefers-reduced-motion`. Animations are cancelled on unmount and paused/resumed on document visibility changes.

## Performance

Source registry data is derived once per frontend payload with `useMemo`:

- Records by source organisation
- Source family rollups
- Source type count
- Organisation date spans
- Narrative labels
- Jurisdiction labels
- Filterable search strings

Splitter dragging updates CSS variables directly and does not rescan public records.

## QA

Completed:

- `npm run typecheck` passed.
- `npm run build` passed.
- Localhost route recheck passed after build:
  - `/source`
  - `/dashboard`
  - `/map`
  - `/density`
  - `/about`
- Header metrics verified after redesign:
  - One aligned dark row.
  - Labels and values visible.
  - No pale floating blocks.
- Source count visible: `PUBLIC RECORDS 3,809`.
- Source registry filter works.
- Source inspector works.
- Right pane scrolls independently.
- Left pane scrolls independently through family and source-type rollup rows.
- Divider reset returns to `38%`.
- Keyboard resize changed the ratio in browser QA.
- Navigation duplicate-label regression fixed.
- No stale hard-coded frontend count values found in `app`, `components`, or `lib`.

Browser QA limitations:

- The in-app browser viewport override did not take effect in this session; it kept reporting the default viewport.
- Some screenshot calls timed out after several captures, so mobile and reduced-motion screenshots could not be captured reliably through the available browser surface.
- The rollup pane was extended with a source-type signal section after QA showed the family-only rollup could fit without scroll movement.

## Screenshots

- Baseline: `data/processed/v2/source_terminal_screenshots/baseline_source_1440x900.png`
- Desktop default split: `data/processed/v2/source_terminal_screenshots/desktop_default_split_1440x900.png`
- Desktop divider dragged left: `data/processed/v2/source_terminal_screenshots/desktop_divider_dragged_left.png`
- Desktop divider dragged right: `data/processed/v2/source_terminal_screenshots/desktop_divider_dragged_right.png`
- Left pane scroll attempt: `data/processed/v2/source_terminal_screenshots/left_pane_scrolled_independently.png`
- Right pane scrolled independently: `data/processed/v2/source_terminal_screenshots/right_pane_scrolled_independently.png`
- Active filter: `data/processed/v2/source_terminal_screenshots/active_filter.png`
- Selected source inspector: `data/processed/v2/source_terminal_screenshots/selected_source_inspector.png`

## Build Result

`npm run build` passed with Next.js `16.2.9`.

## Remaining Limitations

- Mobile screenshot capture could not be completed because the in-app browser viewport override did not apply and standalone Playwright is not installed locally.
- Reduced-motion behavior was verified by code path/CSS media query, but not screenshot-captured.
- The left rollup now contains both family and source-type aggregates; it is denser than the first pass, but remains frontend-derived and public-data-only.
