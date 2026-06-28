# Theme Contrast Audit

Date: 2026-06-28
Branch: release/theme-contrast-fix
Starting commit: 45b273ced2cc4694ba9f1b4b63d93ba3fbf3e66f

## Result

Current light mode was treated as failed release QA. The failure was not a single colour choice: light mode inherited many dark-theme component styles, including pale text, dark translucent panels, low-opacity secondary labels, map drop shadows, and parent overlay effects.

Light mode has been corrected and remains enabled. It is no longer dependent on SIGNAL HIGH for basic readability.

## Theme Implementation Findings

Theme state is implemented in `components/signal-gain-control.tsx` with `data-theme` and `data-signal-gain` applied to `document.documentElement`. Persistence uses `aus-archive-theme` and `aus-archive-signal-gain` in localStorage.

Theme variables are defined in `app/globals.css`. Before this fix, the root theme provided only coarse variables such as `--bg`, `--panel`, `--ink`, `--muted`, and signal colours. Many route-specific elements still used hard-coded dark-theme RGBA values.

The first-paint theme application was missing. A small inline script was added in `app/layout.tsx` so stored theme/signal values apply before hydration.

## Missing Light-Mode Coverage

The following areas had missing or incomplete light-mode remapping:

- About page body text, module text, flow labels, status cells, command strip, and action buttons.
- Map boundary, state fill, state labels, terrain pattern layer, source legend, readout panels, and marker source colours.
- Source register headers, rows, rollups, secondary text, inspector, filters, splitter, and scrollbars.
- Dashboard chart panels, labels, SVG microtext, relation graph nodes, source field preview, and time cutter.
- Density band panels, matrix cells, signal rows, rail marks, and footer labels.

## Parent Opacity / Blend Findings

No major text parent was using a single low opacity value, but the global terminal overlays were too visible in light mode:

- `.terminal-shell::before` used `mix-blend-mode: multiply` and opacity `0.1` in light mode.
- `.view-area::after` used opacity `0.22` in light mode.
- These overlays contributed to the washed-out impression and reduced map/text clarity.

The light-mode overlay opacity is now reduced, and the content surface uses stronger semantic tokens instead of relying on SIGNAL HIGH.

## Map-Specific Findings

Map light mode had the clearest theme failure:

- Australia and state boundaries were too low in hierarchy.
- Terrain texture was either washed out or visually muddy.
- Some marker source tones were too pale for a light terrain.
- Right-side readout panels inherited dark translucent panel styles.

Map-specific variables were added for land fill, state fill, boundary, coast, terrain opacity, and dot tones. Public map dots remain pure solid dots with no stroke, no halo, no blur, and no permanent ring.

## Manual Contrast Checks

Checked at normal laptop brightness:

- About light-normal: body text, title, status panel, command strip, and buttons readable.
- Map light-normal: coastline, state borders, state labels, terrain cues, source dots, readout, mini state boxes, and legend readable.
- Source light-normal: rollup table, registry rows, selected row, inspector, and filter line readable.
- Dashboard light-normal: relation labels, field panels, time cutter, and source field charts readable.
- Density light-normal: date bands, matrix cells, labels, and signal bars readable.

SIGNAL HIGH increases line and signal emphasis only; it is not required for ordinary reading.
