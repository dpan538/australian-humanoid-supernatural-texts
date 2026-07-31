# AusFigures mobile design system

This system applies only at `max-width: 720px`. It must not change the desktop archive shell, its geometry, or its interaction model.

## Shape contract

- Visible cards, controls, charts, badges, and nested surfaces use the shared mobile radius scale.
- A rounded container must never contain a visible sharp-cornered rectangle.
- Use negative space, a hairline divider, a circle, a pill, or a smaller rounded surface to separate content.
- Transparent structural wrappers may remain rectangular because they do not create a visible surface.
- Fixed navigation is a visibly separated pill in both themes. Its active illumination is another rounded surface; sharp trapezoids, rectangular selection blocks, and beams that hide the parent radius are forbidden.
- Map regions use direct state and territory abbreviations over negative space. Do not place those labels inside circular badges.
- The mobile map is one always-visible analysis card. Its silhouette is fill- and dot-led; do not add a fragile traced coastline over the state geometry.

## Contrast and colour

- Small statistic cards use saturated colour with dark text; do not place one high-contrast black/white cell beside otherwise soft coloured cells.
- Light mode uses a restrained material palette: warm paper, olive, concrete grey, earth brown, analytical orange, and a limited signal yellow. It must not increase luminance uniformly or read as a candy-coloured consumer dashboard.
- Dark mode uses near-black backgrounds and warm light ink, with the same olive, earth, orange, and signal roles at controlled saturation.
- Bright signal colour is reserved for analytical emphasis, selection, and key counts; large research surfaces use quieter material colours.
- Text and icons on the same colour role must use the same contrast mapping.
- Compact analysis cards may use high-luminance sky, lime, coral, and violet surfaces with near-black text. Do not pair a dark chromatic surface with dark type.
- Background gradients are not part of the mobile system.

## Type and spacing

- Body copy targets 15–16px or larger; map labels and interactive icons must remain readable after SVG scaling.
- Display type is lighter than desktop terminal headings and uses manually tuned tracking.
- Section labels, card titles, metrics, and body copy share one vertical rhythm; a title must not appear as an unrelated typographic layer above its content.
- Card titles wrap at word boundaries. A word must not be split so that a final line contains one orphan letter.
- Compact cards are content-driven and use one shared minimum height. Do not create visual variety with arbitrary `nth-child` heights or leave a large empty middle row.
- Card-to-card and section-to-card spacing use the shared deck gap. Route-specific desktop padding and grid gaps must be reset at the mobile card boundary.
- Compact and expanded cards use the same outer gutter and always occupy the full deck width.
- Figure editorial summaries show six readable lines by default and expose an explicit expand/collapse action for the complete archive summary.
- Parallel analysis cards must encode real derived values with varied visual structures such as matrices, stacked columns, rings, and proportional blocks. A decorative line alone is not an analysis view.
- Map and Density each expose one large, always-visible primary visualisation before compact or expandable detail modules. The Map card may pair regional volume with a small period-density signal, but both remain subordinate to the map and selected mapped-record count.
- Source is visual-first: family volume, organisation composition, and leading-register distribution remain visible; source-family, role, and organisation lists are grouped into the final collapsed detail card.
- Compact analysis cards are visual-first: one primary number, one short label, and one bounded chart. Do not add category headers, sequence numbers, or explanatory paragraphs to that compact state.
- The chart is the dominant object inside an analysis card. Its occupied area must exceed the metric type, and a smaller chart may not be used merely to decorate a large number.
- Primary compact metrics use at least 24px type at 320px. A data-bearing compact preview uses at least 34px of chart height; direct analysis cards reserve at least 96px for their chart.
- Loader and hero artwork keep a minimum 12px inset from every rounded edge. A label must retain its own bottom safe space and may never touch or cross the container boundary.
- A card presented as an analysis view needs a real chart, matrix, ring, map, or proportional block. Small low-volume values may instead form one concise row of direct-number cards; do not invent a chart where the value does not support one.
- Static pagination dots are forbidden. Dots may appear as pagination only when the content is a real horizontal swipe/scroll-snap sequence with an active index.
- Two closely related charts use one full-width swipe card instead of a compressed side-by-side split. The track uses native horizontal scroll snap, a moving progress rail, an active chart title, and finger swiping; do not add desktop-style tab buttons.
- Repeated numeric summaries either become a meaningful chart or a horizontal swipe sequence; they must not consume a long vertical stack as near-identical text cards.
- A route hero and the first card may not repeat the same count or summary. Keep the hero summary and delete the duplicate card, or remove the hero metric and let the chart card own it.
- Fixed navigation may overlap the page background but must not hide the primary chart at the route's initial scroll position.
- Parallel analysis cards must not present several percentages as if they form one additive system. Prefer legible record counts, ranks, or spans while the chart carries the proportional relationship.
- A figure with no accepted public-text record is outside the public Figure index: it is not searchable, receives no detail path, and must never become an empty-state card.
- An expand arrow is sufficient interaction language for compact research modules. Do not repeat generic labels such as `Read`; use that space for a small, data-bearing preview or remove it and reduce the card height.

## Navigation and motion

- Top left is the sun/moon theme control; top right is the search magnifier.
- Bottom order is About, Map, Density, Source, Figures. Icons have accessible labels even when visible text is omitted.
- Standard phone navigation icons are at least 36px; top controls use 32px artwork inside a 48px touch target.
- The active navigation light is centred on the icon geometry, not merely the link column, and remains centred after route motion settles.
- The Figures symbol is a dictionary/book with a letterform, never a constellation, star, account, or profile avatar.
- Only one primary card expands at a time. Expansion uses natural height, staggered content, and the shared easing tokens.
- Every expandable card uses the shared open and close timeline plus a visible press response for touch. Press feedback must not change layout or create horizontal overflow.
- Route entry uses a restrained upward reveal as cards enter the viewport. Bottom-navigation icons respond immediately to touch, the rounded active illumination travels between routes, and theme changes use a spatial light-on/light-off reveal followed by surface settling.
- The mobile loading stage is one compact rounded square with no exterior caption or decorative clock marks. It presents exactly three isolated phases in order: a large Australia map with `Australia`, archive counts, then a circular index signal. The map and ring artwork dominate the reduced square, use muted research colours, and never show clock ticks. Map outlines are quiet enough to support the silhouette instead of becoming the loading graphic. Phases do not overlap; a reduced-motion fallback skips the sequence.
- The desktop terminal loader is never rendered on the mobile first paint, including the pre-hydration frame.
- All motion must respect `prefers-reduced-motion`.

## Mobile editorial scope

- About is a concise mobile orientation surface: scope, method and rigour, limits and ethics, and the open project link.
- Full citation samples and desktop-level methodological detail stay on the desktop About surface; the mobile shell does not reproduce them.

## Route audit

- Map: large state-aware map and selected mapped count are directly visible. Regional volume and period density share one full-width, horizontally swipable chart card rather than two compressed columns.
- Density: annual series is directly visible. High-volume periods receive varied ring, column, step, or arc analysis cards; the three low-volume periods become one direct-number row. Repeating the same bar or dot matrix across every period is not permitted.
- Dashboard: the public total appears once in the hero; the four parallel cards own mapped, period, source and figure counts with a matrix, columns, ring, or proportional blocks. No second summary deck repeats those values.
- Source: family volume, organisation composition and leading-register distribution are directly visible; lists appear only in the final collapsed card.
- Figures: the archive summary is six lines by default; no duplicate Overview card repeats its total. Presence, time, region/source, record and related modules add distinct information with data-bearing previews.
- About: public, mapped and source counts each carry a compact chart; Scope uses three count-specific visual encodings before its expandable research note.
