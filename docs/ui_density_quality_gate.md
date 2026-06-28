# Density UI Quality Gate

The Density page must pass `npm run qa:density-ui` before release changes are accepted.

## Minimum Font Sizes

- Core visible Density text: 14px minimum.
- Chart axis and chart data labels: 12px minimum.
- Period, card, and panel labels: 13px minimum.
- Main period numeric counts: 32px minimum.

## Contrast

- Axe `color-contrast` checks must pass for `.density-view`.
- SVG chart text must meet at least 4.5:1 contrast against its chart background.
- Primary SVG chart marks must meet at least 3:1 contrast against their chart background.

## Mobile Overflow

At 390 x 844, the Density page and its panels must not create horizontal overflow. Charts should fit the available panel width rather than requiring sideways page or panel scrolling.

## Scroll Snap

Density must not use `scroll-snap-type` or `scroll-snap-align`. The page should scroll normally when the viewport is small.

## Public Labels

Public UI must not expose engineering or process labels, including:

- `FIELD 01`
- `FIELD 02`
- `FIELD 03`
- `PERIOD METHOD COMPARATOR`
- `ANALYTICAL FIELD`

## Chart Readability

Density charts must be actual SVG visualizations with readable axes and marks. ASCII/text-character blocks are not acceptable as the primary data visualization.
