# Performance Budget

The first release is optimized for research usability on modern laptops and acceptable small-screen use. It is not a low-bandwidth mobile-first product.

## Initial Load

Targets:

- Dashboard should become interactive within an acceptable time on a modern laptop.
- Frontend JSON size must be recorded in `data/processed/v2/release_baseline.md`.
- Large JSON should remain a static data file and should not be bundled directly into route JavaScript.
- No blocking long animation should delay first paint.

Current measured value:

- `public/data/frontend-data.json`: 20,717,839 bytes in the generated release baseline.

## Map

Targets:

- 1200-1500 markers should render without severe lag.
- No continuous animation on all markers.
- No SVG filters on all markers.
- Avoid per-marker React event handlers where delegation or grouped interaction is already available.
- Hover and active marker feedback should feel responsive.

Current baseline:

- Public map flags: 1206.

## Dashboard

Targets:

- Derived aggregates should be memoized.
- Avoid full-corpus sort/scan on every hover.
- Avoid thousands of hidden DOM nodes.
- Panel animations should not trigger expensive recomputation.

## Source

Targets:

- Source rows should scroll efficiently.
- Splitter drag should not recompute source aggregates.
- Filter should be debounced or efficient for the current data scale.

Current baseline:

- Public source organisations in the release audit: 42 total registered organisations, 33 with public records.

## Mobile And Small Screen

Targets:

- No horizontal page overflow.
- No requirement for hover-only information.
- Map remains readable enough for exploratory use.
- Source and dashboard fall back to stacked or scrollable views.

## Route Size Recording

Route server JavaScript byte sizes are recorded in `data/processed/v2/release_baseline.md` when `.next/server/app-paths-manifest.json` exists. Re-run `npm run build` before publishing and regenerate the baseline if route output changes.

