# Frontend Optimization Report

## Localhost URL

- `http://127.0.0.1:3000`
- Required routes checked: `/`, `/dashboard`, `/map`, `/density`, `/source`, `/about`
- `/` redirects to `/dashboard`; destination returned HTTP 200.

## Views Inspected

- Dashboard
- Map
- Density
- Source
- About
- Record card overlay

## Current Data Volume

The collection process was still running during this frontend pass, so these are QA snapshot values only, not canonical final counts.

- Snapshot data generated at: `2026-06-22T09:59:36+00:00`
- `frontend-data.json`: 20,394,494 bytes
- Public records: 3,624
- Map flags: 1,057
- Map points: 1,057
- Broad locations: 1,991
- Sources: 41
- Queries: 328
- Figures: 32

## Data Loading Findings

- Before this pass, each route imported `public/data/frontend-data.json` through `lib/frontend-data.ts` and passed the full payload into the client component boundary.
- The frontend now fetches `/data/frontend-data.json` as a static asset from `ArchiveTerminalRoute`.
- Route HTML now prerenders a lightweight loading shell instead of embedding the full records payload.
- Full record details are still loaded eagerly once a data view mounts, but they are no longer bundled into the initial route JavaScript or prerendered page payload.
- Production App Router shared route JS measured from `.next/server/app/dashboard/page/build-manifest.json`: 569,220 bytes across shared chunks.
- Browser QA showed `/data/frontend-data.json` transferring as a separate compressed static request of about 2.44 MB for the 20.4 MB JSON snapshot.

## Component Changes

- Added `ArchiveTerminalRoute` and `ArchiveTerminalShell` while preserving route structure and the archive-terminal visual identity.
- Centralized derived frontend data in one memoized pass: record lookup, sorted navigation records, map flags, source rows, query counts, figure counts, date-band samples, and mapped state counts.
- Changed dashboard, map, density, and source views to consume derived structures rather than rescanning and resorting records during render.
- Kept the existing record-card appearance, but added dialog labeling, focus on open, Escape close, and focus return.

## Performance Changes

- Removed static JSON import from route modules.
- Map now renders from `map_flags`, deduplicated by `record_id`, with one public flag per record.
- Map flag interactions use delegated event handling at the flag layer and memoized marker components.
- Large flag sets disable per-flag arrival animation.
- Density date-band samples and figure rails use precomputed lookups.
- Overlay previous/next navigation uses pre-sorted indexes instead of sorting all records on card open.

## Desktop Findings

- Checked 1440 x 900.
- All required routes loaded with no Next.js error overlay.
- No horizontal overflow detected.
- Dashboard, density, map, source, about, and overlay remained usable.

## Mobile And Tablet Findings

- Checked 1024 x 768 and 390 x 844.
- No horizontal overflow detected.
- Map remained legible and rendered all flags for the active snapshot.
- Source register has a bounded scroll area.
- Record overlay fits mobile viewport and scrolls when needed.
- Density stacks into responsive grids.

## Accessibility Changes

- Preserved `prefers-reduced-motion` handling and added a large-map animation suppression path.
- Added global keyboard-visible focus styles.
- Converted state mini controls to semantic buttons.
- Added accessible dialog labeling with `aria-labelledby`.
- Escape closes the overlay.
- Focus is moved to the close button on open and returned to the invoking marker/control on close.
- Map flags remain keyboard focusable and open with Enter or Space.

## Runtime QA

- HTTP route checks passed for all requested routes.
- Browser checks passed at 1440 x 900, 1024 x 768, and 390 x 844.
- Interaction QA passed:
  - map DOM flags matched JSON map flags at final QA snapshot: 1,057 / 1,057;
  - selected marker opened the correct overlay;
  - Arrow navigation advanced within region;
  - Escape closed the overlay;
  - focus returned to the selected marker;
  - source register scrolled within its bounded panel.

## Remaining Defects

- Browser console reports a 404 for a missing default resource, likely favicon; no application route or data load failed.
- At the QA snapshot, 20 `map_flags` referenced record IDs that were not present in `records`. The UI now renders these as summary-only map-flag cards rather than discarding the flags. This should be reconciled in the data export after the collection sprint settles.
- Full record details are fetched eagerly per data-view load. A future pass could split compact summaries from lazy record detail fetches, but this pass avoided changing the frontend-data contract.

## Files Changed

- `app/dashboard/page.tsx`
- `app/map/page.tsx`
- `app/density/page.tsx`
- `app/source/page.tsx`
- `app/globals.css`
- `components/archive-terminal.tsx`
- `lib/frontend-data.ts`
- `data/processed/v2/frontend_optimization_report.md`

## Validation

- `npm run typecheck -- --incremental false`: passed
- `python3 scripts/run_tests.py`: passed, including `tests/test_frontend_data_contract.py`
- `npm run build`: passed

## Production Build Result

`npm run build` completed successfully with static prerendered routes:

- `/`
- `/_not-found`
- `/about`
- `/dashboard`
- `/density`
- `/map`
- `/source`
