# Frontend QA Checklist

Run this checklist before tagging the first public release.

## Browser Smoke

- Chrome desktop loads all routes.
- Safari desktop loads all routes if available.
- Mobile simulator or responsive mode loads all routes.
- No console errors.
- No hydration warnings.
- No duplicate React key warnings.

## Routes

- `/about`
- `/map`
- `/dashboard`
- `/density`
- `/source`

## Data

- Public data counts reconcile with `data/processed/v2/release_baseline.md`.
- `mapped_record_count == map_points.length == map_flags.length`.
- Static JSON loads from `/data/frontend-data.json`.
- Source page source totals reconcile with the release validation report.

## Interaction

- Keyboard navigation reaches actionable controls.
- Escape closes record overlay.
- Buttons have visible focus.
- Marker hover and selected marker states are legible.
- State hover states are legible.
- Record overlay navigation works.

## Accessibility Modes

- Reduced motion does not block comprehension.
- High contrast or signal gain remains readable.
- Information is not hover-only on small screens.

