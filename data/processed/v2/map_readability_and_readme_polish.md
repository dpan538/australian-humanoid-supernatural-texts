# Map readability and README polish

## Starting state

- Starting branch: `codex/about-and-ambient-terminal-motion`
- Task branch: `codex/map-clarity-readme-polish`
- Starting commit: `3d4d9f911e1cd705c999be607e4a5c3289ea7e46`
- `origin/main`: `96383443a30d8b7558784d73ba730f538004148e`
- Localhost: reused existing repository dev server on PID `73462`, listening at `127.0.0.1:3000`
- Preserved unrelated dirty collection/data/doc files; no reset, clean, or data export changes were performed.

## Map marker changes

- Replaced the layered map marker glyph with the lightweight structure:
  - one invisible `.record-flag-hit` circle;
  - one visible `.record-flag-dot` circle;
  - one optional `.record-flag-active-ring` circle only for the active marker.
- Increased the final pure-dot marker radius by roughly 10% after screenshot review:
  - default marker radius: `2.8px`;
  - state-linked marker radius: `3.7px`;
  - active marker radius: `5.2px`;
  - legend dot radius: `3.3px`.
- Removed the permanent outer ring, under-ring, halo-like opacity stack, and ring/core glyph wrappers from every default marker.
- Kept the existing delegated map event handlers and record overlay semantics.
- Kept deterministic collision offsets, but capped the largest presentation-only offset at `4px`.
- Updated the source-tone legend to display the same pure-dot glyph used on the map.

## Removed blur, halo, filter, and performance hazards

- Removed `.record-flag-ring`, `.record-flag-core`, `.record-flag-under-ring`, `.record-flag-glyph`, and `.record-flag-symbol` from the marker DOM and CSS.
- Default markers no longer use blur, filters, shadows, permanent glows, animated strokes, or ongoing ambient loops.
- Marker state changes are CSS-driven with opacity/fill/stroke transitions only.
- Active marker bloom is a one-shot ring on the selected/hovered marker only.
- Browser QA found no CSS animations running on sampled default map flags after the entrance settled.

## Current mapped marker count

- Frontend-rendered marker groups: `1206`
- Unique rendered record IDs: `1206`
- Visible map dots in `.record-flag-layer`: `1206`
- Old ring/glyph pieces after refactor: `0`
- Default rendered marker radius after final adjustment: `2.8`
- Count formatting: map readout contains `1206`; no `1,206` found in the map readout.

## Anime.js changes

- Kept the existing bounded Anime.js entrance sequence.
- Retargeted growth animation from `.record-flag-glyph` to `.record-flag-dot`.
- Entrance still uses 12 west-to-east buckets with bounded timing and does not replay on hover, state hover, overlay open/close, or resize.
- Reduced-motion path immediately sets all dots visible at `opacity: 1` and `scale(1)`.

## Idle CPU and interaction observations

- Hovering NSW and WA state controls brightened state-linked flags and dimmed other flags without replaying the full entrance sequence.
- Opening an active marker overlay remained responsive in browser interaction testing.
- Browser console check after reload reported no runtime errors, warnings, hydration warnings, or duplicate key messages from the app.
- Full browser performance recording was not run; interaction testing did not show visible lag after the ring/halo removal.

## Colour and brightness diagnosis

Findings from the CSS audit:

- Important map markers previously depended on low-opacity rings and under-rings, creating a foggy cluster effect over dense regions.
- The global terminal shell stacked a scanline blend layer and a grid noise layer over an already-dark background.
- Several data marks and secondary labels used opacity values near `0.2-0.4`; that was acceptable for texture, but too weak for primary map signals.
- No browser API can detect the user's physical screen brightness, so the fix is design-side contrast and a manual signal gain.

## Colour variable changes

- Slightly brightened the default terminal palette without creating a neon or light theme:
  - background/panel values remain near black;
  - ivory, cyan, green, amber, violet, and dashboard muted variables are clearer;
  - default map dots now use opacity around `0.93-1` rather than relying on low-opacity rings.
- Reduced default grid/noise opacity slightly so primary data marks carry more visual weight.
- Added `@media (prefers-contrast: more)` to strengthen text, focus outlines, and map dot opacity while reducing decorative noise.

## SIGNAL NORMAL / HIGH behavior

- Added `SignalGainControl` as a small persistent terminal control.
- Default mode: `SIGNAL NORMAL`.
- High mode: `SIGNAL HIGH`.
- The mode persists in `localStorage` as `aus-archive-signal-gain`.
- The active mode is applied to the root as `data-signal-gain="normal|high"`.
- HIGH mode increases text and marker brightness, strengthens relevant borders, and reduces decorative noise opacity.
- No public data, counts, routes, or layout semantics are changed by the control.

## README structure changes

- Rewrote the README opening around the current title:
  `Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters`.
- Added clearer sections:
  - What this project is
  - What this project is not
  - Current public interface
  - Data model
  - Source and ethics policy
  - Running locally
  - Data workflow
  - Repository structure
  - Citation
  - Licensing
- Moved legacy working-title language out of the lead and marked it as provenance.
- Updated citation examples to the current project title.
- Preserved local setup, build, V2 workflow, manual import, and export commands.
- Clarified split licensing and retained the visual-interface license explanation.

## Repository metadata

`gh` was not available in this environment, so repository About metadata was not edited remotely.

Manual command:

```sh
gh repo edit dpan538/australian-humanoid-supernatural-texts \
  --description "Typed public-text archive and research display for Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings." \
  --add-topic digital-humanities \
  --add-topic public-archive \
  --add-topic folklore \
  --add-topic australian-history \
  --add-topic data-visualization \
  --add-topic research-interface \
  --add-topic supernatural-narratives \
  --add-topic provenance
```

## Screenshots

- Before marker simplification: `data/processed/v2/map_readability_readme_screenshots/map_before_marker_simplification.png`
- After pure-dot markers: `data/processed/v2/map_readability_readme_screenshots/map_after_pure_dot_markers.png`
- Map hover state, NSW: `data/processed/v2/map_readability_readme_screenshots/map_hover_nsw_state.png`
- Map hover state, WA: `data/processed/v2/map_readability_readme_screenshots/map_hover_wa_state.png`
- Active marker overlay: `data/processed/v2/map_readability_readme_screenshots/map_active_marker_overlay.png`
- Map SIGNAL NORMAL: `data/processed/v2/map_readability_readme_screenshots/map_signal_normal.png`
- Map SIGNAL HIGH: `data/processed/v2/map_readability_readme_screenshots/map_signal_high.png`
- Source SIGNAL NORMAL: `data/processed/v2/map_readability_readme_screenshots/source_signal_normal.png`
- Source SIGNAL HIGH: `data/processed/v2/map_readability_readme_screenshots/source_signal_high.png`
- About after colour adjustment: `data/processed/v2/map_readability_readme_screenshots/about_after_color_adjustment.png`
- Mobile map: `data/processed/v2/map_readability_readme_screenshots/mobile_map_pure_dots.png`

## Build and route result

- `npm run build`: passed.
- Rechecked after build:
  - `http://127.0.0.1:3000/map`
  - `http://127.0.0.1:3000/about`
  - `http://127.0.0.1:3000/source`
  - `http://127.0.0.1:3000/dashboard`
  - `http://127.0.0.1:3000/density`
- All route checks passed.
- Localhost remains running on `http://127.0.0.1:3000`.

## Remaining limitations

- GitHub repository metadata was not updated because `gh` was unavailable.
- CPU performance was assessed through interaction and animation checks, not a saved browser performance trace.
- Screenshots are retained as local QA artifacts and listed here; only scoped frontend/README/report files should be committed.
