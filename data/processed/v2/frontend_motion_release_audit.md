# Frontend Motion Release Audit

Date: 2026-06-28
Branch: release/theme-contrast-fix

## Motion Tiers

Release motion is classified as:

- Tier A data reveal: runs once, reveals data structure, bounded duration.
- Tier B interaction motion: short hover/selection/panel feedback.
- Tier C ambient terminal motion: subtle loops on a small number of non-text indicators.

## Map

Status: stable

Map flags use a chronological accumulation reveal. Records are grouped by year bucket or date band, earlier buckets appear before later buckets, and points settle into static pure colour dots.

The reveal remains quantity-focused: dots appear in chronological batches instead of each point fading or scaling slowly. There is no random stagger, no west-to-east ordering, and no continuous all-marker animation.

The current timing uses bounded chronological chunks:

- chunk size: 30 record dots
- chunk interval: 42ms
- bucket gap: 120ms
- expected total: about 2.8 to 3.0 seconds for the current 1206 mapped records

Theme and signal toggles do not change the map flag signature and should not replay the heavy reveal.

## Ambient Loops

Status: acceptable_with_warnings

About and Source retain subtle terminal life on small non-text indicators such as LEDs, raster cells, divider markers, and flow lines. These are acceptable because they are not applied to text, numbers, tables, or all records.

Map has no continuous animation on all markers. Active marker ring animation is limited to the selected marker only.

Dashboard and Density data reveal/interaction animations remain bounded; no release-blocking continuous animation was observed.

## Reduced Motion

Status: stable

The existing `prefers-reduced-motion: reduce` CSS disables animations and transitions and forces map record dots visible. Active marker bloom is disabled under reduced motion.

## Release Notes

No new animation library was added. Anime.js remains the animation system. No pixel effects, glow filters, SVG blur filters, or decorative rosette/collision layouts were introduced.
