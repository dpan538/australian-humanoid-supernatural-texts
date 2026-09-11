# Map page + boot screen redesign — plan (2026-09-11)

Status: **§2, §3 and §5 implemented on 2026-09-11 with the changes recorded in §7; §4 (region
sub-view) is parked by decision.** Written before code so the approach could be checked in. Two small fixes landed with it: the Source header LED lost its halo,
and the loading-screen note now reads "A public source existing does not mean a
supernatural claim is verified." (same wording as About, llms.txt and the index
pages).

Scope is the desktop map (`MapView` in `components/archive-terminal.tsx`). The
mobile shell has its own map and is not covered here.

## 1. Findings

### 1.1 Are all points really plotted?

Yes — and that is part of the problem.

| Measure | Value |
| --- | --- |
| `map_flags` in `frontend-interactive.json` | 1,593 |
| `summary.mapped_record_count` / `map_flag_count` | 1,593 / 1,593 |
| `.record-flag` groups in the DOM | 1,593 (+5 legend rows that reuse the class) |
| Distinct coordinates | **870** |
| Coordinates shared by ≥2 records | 248 |
| Flags sitting on a shared coordinate | **971 (61%)** |
| Largest stacks | QLD 153.415,-28.002 ×35 · VIC Melbourne CBD ×32 · NSW Sydney CBD ×29 · VIC 145.350,-37.833 ×26 · QLD ×16 · TAS ×14 |
| Stacked flags per state | NSW 420 · QLD 284 · VIC 134 · TAS 43 · SA 26 · WA 25 · ACT 20 · NT 19 |

`prepareMapFlagPresentation` jitters identical coordinates by at most ±2.1 / ±1.9
viewBox units; the dot radius is 3.6. A stack of 35 therefore renders as one
slightly fat dot. Every record is drawn; roughly 700 of them are invisible.

**Data-integrity flag (decision needed).** `confidence` on the flags mixes
vocabularies: `high` 701, `medium` 283, `B` 250, `C` 1,
`stage_only_public_report_marker` 350, `stage_only_public_report_index_link` 8.
The 358 `stage_only_*` rows come from `scripts/crawl_ayr_yowie_map.py`, whose own
report says they "require human review before production import". They are on
the production map with `display_precision: precise_point`. Either they have
been reviewed and the label is stale (then normalise it in the export), or they
have not (then they should be shown as a distinct "public report marker" class,
disclosed in the legend, or withheld). The export copies the location row's `confidence` straight through (`scripts/export_frontend_json.py:453`) — there is no review gate at export time. This is the honest answer to "是否足够真实".

### 1.2 Why the map janks (from the code; runtime probe still to run)

1. **Hover re-renders hundreds of React nodes.** `MapFlagMarker` takes
   `active` and `stateLinked` props. Hovering NSW flips `stateLinked` on 663
   markers → 663 re-renders, each rewriting `className` and `r`.
2. **1,593 concurrent CSS transitions.** `.record-flag { transition: opacity
   120ms }` and `.record-flag-dot { transition: fill, r 120ms }`. The layer
   classes `has-state-hover` / `has-hover` change opacity on every flag, so each
   hover change starts ~1,593 transitions.
3. **Pattern-filled terrain repaints the whole map.** `TerrainSurfaceLayer` is
   up to 24 full-viewBox `<rect fill="url(#pattern)">` where the pattern is
   `<text>` glyphs, under `mix-blend-mode: screen`, with `transition: opacity
   130ms` and class swaps (`emphasized/dimmed`) on every state hover. SVG has no
   per-element raster cache: every hover animates a full-canvas text-pattern
   rasterisation for ~8 frames.
4. **3,186 circles + 1,593 focusable groups.** Each flag has a 10-unit hit
   circle and a dot; `pointerover` bubbles from every crossing, so dense areas
   push dozens of state updates per mouse move.
5. `.state-shape` transitions `filter` (no-op now, but keeps the property in the
   transition list).

### 1.3 The bottom-left key

`TerrainLegend` is an SVG group (242×84 units, 13px text ≈ 12px on screen, 0.78
backdrop) at the bottom-left of the canvas. It explains the terrain texture,
which is decorative (opacity 0.08–0.22). Nothing about it — size, position,
weight, colour — ranks it against the REGION readout, the state grid, or FLAG
SOURCE in the right column. The only key that carries information (flag source)
is somewhere else.

## 2. Performance plan (ordered by payoff)

**P1 — static / dynamic split.** Render two stacked SVGs in `.map-canvas`:
a background SVG (terrain, state fills, coast, labels) that receives no props
and never re-renders, and a foreground SVG (state hover outline, flags, active
ring). Drop `mix-blend-mode: screen` (bake the tint into the pattern colours),
drop the terrain `emphasized/dimmed` classes and their transitions. Give the
background container `contain: paint`. Expected effect: hover repaints only the
flag layer.

**P2 — hover through attributes, not React state.** Each flag `<g>` carries
`data-state`; the layer carries `data-hover-state` and `data-hover-record`,
set imperatively from refs. CSS does the rest:
`.record-flag-layer[data-hover-state="NSW"] .record-flag:not([data-state="NSW"])
{ opacity: .42 }`. The active ring and label move into one floating `<g>`
rendered from a single piece of state. `MapFlagMarker` then has no changing
props and never re-renders after mount. Remove the transitions on
`.record-flag` and `.record-flag-dot`; keep a transition only on the single
active ring. (`r` as a CSS property is supported in Chromium and WebKit; Firefox
falls back to the attribute value — acceptable.)

**P3 — hit-testing without 1,593 hit circles.** One `pointermove` listener on
the SVG, coalesced to rAF, converts to viewBox units and looks up a 25×18 grid
bucket index built once from `displayX/Y` (nearest flag within 8 units). This
deletes the `record-flag-hit` circles (−1,593 nodes) and the per-element
`pointerover` storm. Keyboard: replace 1,593 tab stops with roving focus
(arrow keys walk the flags of the hovered or selected state in `growthOrder`),
plus the region sub-view's list (§4), which is the better keyboard path anyway.

**P4 — measure before and after.** Scripted pointer sweep NSW → VIC → QLD → a
dense stack, recording rAF intervals and `PerformanceObserver('longtask')`.
Targets: no long task > 50 ms on hover; sweep at display refresh rate; the
growth animation unchanged.

**P5 — only if P1–P3 fall short:** a `<canvas>` renderer for the dot layer with
the same grid index for hit-testing. Not expected to be necessary at 1,593
points.

Estimated effort P1–P4: 6–8 h.

## 3. Bottom-left key — recommendation

Move the key out of the SVG. The right column becomes one **MAP KEY** panel
with two sections in the same typographic register as the rest of the terminal:

```
> MAP KEY
FLAG SOURCE            TERRAIN
■ Historic newspapers  ^^ range      -- lowland
■ Public web           ~~ upland     .. plain
■ …                    :: desert     == plateau
                       ,, basin
```

plus one disclosure line in the health note: `358 positions come from a public
report map marker` (or nothing, once §1.1 is resolved). The map corner is then
free for the region affordance (`> CLICK A STATE TO OPEN IT`), which is the
interaction the page actually wants people to find.

Alternative if the key must stay on the canvas: an HTML overlay (not SVG text)
at the bottom-left, 0.72rem typewriter, `[ TERRAIN KEY ]` heading, no
translucent backdrop — the same block as above, absolutely positioned. It
would still compete with the readout column; that is why the move is
recommended.

Estimated effort: 2 h.

## 4. Region sub-view — implementation design

**Trigger.** Click on a state path *or* on the `.state-mini` button in the
readout (hover keeps its current preview role). Both get `aria-haspopup="dialog"`.

**Container.** A `<section role="dialog" aria-modal="true">` absolutely
positioned over `.map-canvas` (`inset: 0`), so it is exactly the canvas size;
the readout column stays visible and its state grid becomes the region
switcher while the dialog is open. Grid inside the dialog:

```
┌──────────────────────────────────┬──────────────────────┐
│                                  │  > NSW · New South Wales     [×]  │
│         state map (SVG)          │  PANEL 1  mapped records by period │
│   viewBox = state bbox + 6%      │  PANEL 2  display locations that   │
│   663 dots, stacks spread        │           stack (top 8)            │
│                                  │  paragraph (data-generated)        │
└──────────────────────────────────┴──────────────────────┘
```

Left column ≈ 58 % width, full height; right column holds the close button at
its top-right corner, then the two panels and the paragraph. (If "下方" was
meant literally — panels under the map across the full width — the grid becomes
two rows instead; the same components apply.)

**State map.** Reuse `STATE_SHAPES[code].d` and the existing `displayX/Y`
(already in the 1000×720 viewBox space). Compute each state's bbox once from
the path (`getBBox()` on the hidden main path at mount, or precomputed into
`lib/au-map-data.ts` — precomputing is preferable: no layout read, no SSR
mismatch). Set `viewBox` to the bbox padded 6 %, and scale dot radius by
`bboxWidth / 1000` so dots keep screen size. Tasmania and ACT then get roughly
10× more room; NSW/QLD about 3×.

**Spreading stacks.** For coordinates shared by n ≥ 2 records, arrange the n
dots on a sunflower (phyllotaxis) spiral around the true point with spacing
= 2.4 dot radii; label the true point with `×n` when n ≥ 5. Deterministic
(sorted by `record_id`), no randomness, no simulation. The true location is
still marked (a small hollow ring), so the display stays honest about where the
records actually point.

**Panel 1 — mapped records by period.** Counts per `date_band` for the state
(server-side numbers, block bars like the About typology). Panel 2 — display
locations that stack: the top 8 shared coordinates with their place name
(`map_place_name` / flag `title`) and count; hovering a row highlights those
dots. This is the panel that explains what the overview cannot show.

**Paragraph — generated from data, not prose we maintain.** Template:
"Queensland holds 499 of 1,593 mapped records (31 %). 284 of them share a
display location with at least one other record; the densest is Springbrook
(35 records). Markers are public display locations, not proof, habitats, or
populations." Every number comes from the same arrays the panels use.

**Interaction.** Dot hover → the same label as the main map; dot click →
`onSelectRecord` (existing record overlay, which already stacks above the map).
Close: × button, `Esc`, click on the readout's active state again. Focus is
trapped inside the dialog and returned to the trigger on close. Optional
`?region=QLD` via `history.replaceState` so a region can be linked — cheap,
worth doing.

**Performance.** ≤ 663 dots, no terrain, no patterns, no blend mode; the same
attribute-driven hover as P2. Opening the dialog must not re-render the main
flag layer (the dialog is a sibling of the SVGs, state lives in `MapView`).

**Files.** `components/archive-terminal.tsx` (MapView, new `RegionDialog`,
`buildRegionSummary`), `lib/au-map-data.ts` (bboxes), `app/globals.css`
(`.map-region-dialog*`, dark + light-safe tokens). Data needs nothing new: the
stacks are computed from `map_flags` at load.

Estimated effort: 8–10 h including keyboard/focus work.

## 5. Boot screen — redesign concept (copy needs check-in)

Keep the 16×16 pixel figure; make what it does *mean* something.

- **The walk is real progress.** `loadFrontendData` reads the response as a
  stream and reports bytes received vs. `Content-Length`; the figure's position
  on the track is that ratio (`transform: translateX`, one property). The label
  becomes `READING EXPORT  3.4 / 10.1 MB` — an honest number instead of a
  decorative loop. (The interactive export is 10.1 MB; on a fast connection the
  walk lasts about a second, on a slow one it is the thing you watch.)
- **Checkpoints on the track.** The three boot lines become checkpoints the
  figure passes, each printing a real value once the data is parsed:
  `[■] READ PUBLIC EXPORT · 4,265 records`,
  `[■] INDEX MAPPED RECORDS · 1,593 flags`,
  `[ ] SEPARATE SOURCE FROM CLAIM` (checked last, right before the map draws).
- **A little personality, no glow.** A three-frame sprite (walk A / walk B /
  look-back) as three `<rect>` sets toggled with `steps()`; the current
  `filter: drop-shadow` and the cyan `box-shadow` on the completion line go
  (house rule: no shadow/opacity tricks). The figure walks off the right edge
  as the map's growth animation starts, so the boot hands over to the page
  instead of fading out.
- **Error state** keeps the same layout with the figure stopped at its
  checkpoint and the last line as the message.

Copy to approve before implementation:

1. Title line: `AusFigures` (unchanged).
2. Intro line: `A source-grounded archive of Australian supernatural humanoid narratives.` (unchanged) — or the About hero's first sentence, for consistency.
3. Checkpoints: the three lines above.
4. Progress label: `READING EXPORT {received} / {total} MB`; fallback when the size is unknown: `READING EXPORT {received} MB`.
5. Note: `A public source existing does not mean a supernatural claim is verified.` (already fixed).
6. Error: `Archive data unavailable` / `Refresh the page or try again shortly.` (unchanged).

Estimated effort: 4–5 h.

## 6. Sequence and sign-off

1. Decide §1.1 (the 358 `stage_only_*` flags) — changes what the map claims.
2. P1–P4 performance (measure first, then split, then attributes, then hit-test).
3. Key relocation (§3) — small, do it with P1 since it touches the same SVG.
4. Region sub-view (§4) — approve the layout reading (side column vs. below).
5. Boot screen (§5) — approve the copy list, then implement.

## 7. Implementation record (2026-09-11)

Direction from review: keep the load-time draw, remove the dots' own
animation (hover = label in nearby blank space, click opens), no re-render on
state hover, no further JavaScript, and let the terrain kinds breathe in
rotation with the key. Sub-view parked. What landed:

- **Three stacked SVG planes** (`MapBasePlane`, `MapTerrainPlanes`,
  flag plane) sharing one viewBox. Base and terrain planes are memoised with
  props that never change; they render once at load.
- **Flags**: one `<circle>` per record (was `<g>` + hit circle + dot);
  the hit area is a 6px invisible stroke band (`pointer-events: all`). No
  transitions, no `active`/`stateLinked` props, no hover dimming of other
  states. Hover moves one floating label imperatively (placed left of the
  point in the eastern third, below it near the top edge); click moves one
  static ring and opens the record overlay. The growth animation is unchanged.
- **State hover** swaps a single outline path in the flag plane and updates
  the readout; the flag layer is untouched (measured: 0 mutations during a
  real four-state mouse sweep; 1 long task of 66 ms in 3.3 s).
- **Terrain breathing**: one SVG plane per landform kind; in the dark theme
  each plane's opacity runs a 21 s `terrain-breathe` cycle offset by
  `--kind-index × −3 s`, so the seven kinds take turns (~3 s each) with no
  repaint (compositor opacity, `mix-blend-mode` removed). The bottom-left key
  is now an HTML overlay (`.map-terrain-key`, 0.86rem, `> TERRAIN KEY`) whose
  rows run the same clock, so the lit row is the kind breathing on the map.
  Light theme keeps static terrain (multiply blend) and a light key.
- **Boot screen** as approved: streamed fetch publishes bytes received
  (`READING EXPORT n MB`, or `n / total MB` when the response is not
  content-encoded); the figure's track position is the real ratio
  (`--boot-progress` → `translateX(calc(p × (100cqw − 24px)))`); three-frame
  sprite (walk / walk / look-back) via `steps()`; checkpoints
  `[■] READ PUBLIC EXPORT · 4,265 records`, `[■] INDEX MAPPED RECORDS · 1,593
  flags`, `[■] SEPARATE SOURCE FROM CLAIM` tick in sequence, the completion
  line draws, the figure walks off the right edge, then the map grows. Drop
  shadow and glow removed. Error state stops the figure on the look-back frame.
- Not done: §1.1 decision on the 358 `stage_only_*` flags; §4 sub-view.
