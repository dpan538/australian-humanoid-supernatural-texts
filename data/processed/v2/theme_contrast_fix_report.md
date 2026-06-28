# Theme Contrast Fix Report

Date: 2026-06-28
Branch: release/theme-contrast-fix
Starting commit: 45b273ced2cc4694ba9f1b4b63d93ba3fbf3e66f

## Defects Observed

The current light mode failed release QA. It was washed out, low contrast, and in some places unreadable. The About page showed pale text on a pale background, and the Map page lost boundary, terrain, marker, and readout hierarchy.

This was treated as release blocking. Vercel/domain launch should not proceed with the previous light mode.

## Root Cause

The project had a coarse root variable switch for light mode, but many route components still used dark-theme hard-coded values: pale RGBA text, translucent dark panels, light borders, dark drop shadows, and low-opacity secondary labels.

The global terminal overlays also contributed to the washed-out appearance in light mode.

## Changes Made

- Added semantic theme tokens for terminal surface, ink, muted text, lines, signals, and map roles.
- Added map-specific light tokens for land, state fills, coast, boundaries, terrain opacity, and marker colours.
- Reduced light-mode parent overlay opacity so text and map content are not washed out by the frame effect.
- Added a first-paint theme/signal script in `app/layout.tsx` to apply stored display settings before hydration.
- Remapped About light-mode text, panels, status cells, command strip, flow labels, and buttons.
- Remapped Map light-mode boundary, terrain, state labels, marker tones, source legend, readout panels, and mini state boxes.
- Remapped Source light-mode registry, rollups, filter line, selected row, inspector, splitter, scrollbars, and secondary labels.
- Remapped Dashboard and Density light-mode chart panels, labels, matrix cells, timeline controls, and SVG microtext.
- Adjusted map reveal timing to keep chronological quantity growth smooth without animating individual dots slowly.

## Map Marker Status

Map markers remain:

- one invisible hit circle;
- one visible pure colour dot;
- no black outline;
- no permanent halo;
- no glow or blur filter;
- no decorative collision rosette.

Rendered record marker invariant:

- public mapped record count: 1206
- `map_flags.length`: 1206
- `map_points.length`: 1206
- `.record-flag.precise` rendered groups: 1206
- `.record-flag.precise .record-flag-dot`: 1206

The browser also sees 4 legend sample dots, so the broad selector `.record-flag-dot` returns 1210. The record marker count remains 1206.

## Signal Mode

SIGNAL NORMAL is readable in light mode. SIGNAL HIGH is an enhancement: stronger line/contrast emphasis without changing layout, data, counts, or route state.

## Screenshots

- `data/processed/v2/screenshots/about_dark_normal.png`
- `data/processed/v2/screenshots/about_dark_high.png`
- `data/processed/v2/screenshots/about_light_normal.png`
- `data/processed/v2/screenshots/about_light_high.png`
- `data/processed/v2/screenshots/map_dark_normal.png`
- `data/processed/v2/screenshots/map_dark_high.png`
- `data/processed/v2/screenshots/map_light_normal.png`
- `data/processed/v2/screenshots/map_light_high.png`
- `data/processed/v2/screenshots/source_dark_normal.png`
- `data/processed/v2/screenshots/source_dark_high.png`
- `data/processed/v2/screenshots/source_light_normal.png`
- `data/processed/v2/screenshots/source_light_high.png`
- `data/processed/v2/screenshots/dashboard_light_normal.png`
- `data/processed/v2/screenshots/density_light_normal.png`

## QA

Browser console QA: no runtime errors, hydration warnings, duplicate key warnings, theme toggle errors, or animation cleanup errors observed.

Routes checked:

- `/about`
- `/map`
- `/dashboard`
- `/density`
- `/source`

Build result: `npm run build` passed with all app routes statically prerendered.

Localhost route verification after build: all required `curl --fail` checks passed.

Server left running:

- URL: http://127.0.0.1:3000
- PID: 24161

## Light Mode Status

Light mode passed the focused release-readability QA and remains enabled.

## Remaining Limitations

This is still a desktop-first interface with small-screen adaptations, not a dedicated mobile visual redesign. No canonical data, SQLite, collection scripts, map eligibility, frontend export semantics, public record counts, or route structure were changed.
