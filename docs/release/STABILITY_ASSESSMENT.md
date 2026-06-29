# Stability Assessment

Release stability is evaluated for local development, production deployment, data update, interaction load, and error states.

## Local Development

Classification: `acceptable_with_warnings`

- `npm run dev` is expected to serve the Next.js app locally.
- Route availability is checked at `/about`, `/map`, `/dashboard`, `/density`, and `/source`.
- Fast Refresh may show dev-only animation or hydration noise; this is not automatically release-blocking unless it persists in production build.
- Large `frontend-data.json` loading is acceptable on a modern laptop, but the file size should be tracked in the release baseline.

## Production Static Deployment

Classification: `stable`

- `npm run build` must pass.
- Routes should pre-render or build cleanly under the current Next.js configuration.
- `public/data/frontend-data.json` must be available at `/data/frontend-data.json`.
- Vercel or equivalent static hosting is acceptable if JSON paths and cache behavior are verified after deploy.

## Data Update

Classification: `stable`

Data pipeline sequence when the local Python/data environment is ready:

```sh
make export-frontend
make validate-v2
make audit-v2
npm run build
```

The frontend JSON is generated from SQLite. It should not be manually edited. The map invariant must be confirmed after every export.

For static Vercel frontend deployment, `public/data/frontend-data.json` may be treated as the prebuilt public data contract when it already exists and `npm run build` plus `python3 scripts/check_vercel_release.py` pass.

## Interaction Load

Classification: `acceptable_with_warnings`

- Map with 1200+ markers is within the first-release target.
- Dashboard with 3500-4000 records is acceptable when derived aggregates are memoized.
- Source page with dozens of source organisations is acceptable.
- Record overlay navigation, state hover, and marker hover require manual smoke testing.
- Known warning: source concentration and large JSON size should be monitored, but neither currently blocks release.

## Error States

Classification: `acceptable_with_warnings`

Manual checks should cover:

- frontend JSON missing;
- frontend JSON invalid;
- no map flags;
- record with missing source;
- record with missing title;
- narrow viewport;
- reduced motion;
- high contrast or signal-gain mode.

The release validator checks missing title/source and invalid JSON. Runtime error-state presentation remains a manual QA item.
