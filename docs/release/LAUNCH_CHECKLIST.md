# Launch Checklist

Use this checklist immediately before a production release.

## Frontend Launch Gate

- [ ] `package-lock.json` exists and matches `package.json`.
- [ ] `public/data/frontend-data.json` exists and is intended public data.
- [ ] Run `npm ci`.
- [ ] Run `npm run typecheck`.
- [ ] Run `npm run build`.
- [ ] Run `python3 scripts/check_vercel_release.py`.
- [ ] No `.env`, `.vercel`, tokens, local databases, Playwright reports, traces, logs, or build artifacts are staged.

## Domain Gate

- [ ] Add `ausfigures.com` to the Vercel project.
- [ ] Add `www.ausfigures.com` if redirect is desired.
- [ ] Configure DNS records exactly as Vercel recommends.
- [ ] Wait for Vercel domain verification.
- [ ] Confirm SSL certificate provisioning.
- [ ] Confirm `www.ausfigures.com` redirects to `ausfigures.com`.
- [ ] Confirm `https://ausfigures.com/` loads the index map.
- [ ] Confirm Vercel preview URLs are not used as production canonical URLs.

## Internet Discovery Gate

- [ ] `/robots.txt` allows public crawling and references `https://ausfigures.com/sitemap.xml`.
- [ ] `/sitemap.xml` lists only public HTML routes on `https://ausfigures.com`, including the research topic entry points.
- [ ] `/llms.txt` contains only public, non-sensitive launch guidance.
- [ ] `/llms-full.txt` contains expanded public-safe AI/search context.
- [ ] Route metadata uses restrained public-text archive framing.
- [ ] Dataset JSON-LD includes `license`, valid `spatialCoverage`, and public data distribution metadata.
- [ ] Root index appears as the main sitemap entry.
- [ ] `/opengraph-image` and `/twitter-image` return image/png social cards with research-safe framing.
- [ ] `/manifest.webmanifest` and `/apple-icon` return browser identity metadata for Chrome/Safari.
- [ ] `www.ausfigures.com` permanently redirects to `https://ausfigures.com`.
- [ ] README has the production link and canonical-domain note.

## Research Release Gate

- [ ] Citation guidance is ready.
- [ ] Split licensing remains intact.
- [ ] Source and ethics wording is preserved.
- [ ] Confirm restricted, suppressed, rejected, scope-excluded, or non-public records are absent from public exports.
- [ ] Review Indigenous-related and culturally sensitive records for terminology, publicness, source voice, and display mode.
- [ ] Confirm no corpus counts were hard-coded in UI or metadata.

## Data Pipeline Gate

- [ ] Run `make export-frontend` only when the local Python/data environment is complete and the workspace data state is clean.
- [ ] Run `make audit-v2` with a timeout when the data environment is ready.
- [ ] Run `make validate-v2` with a timeout when the data environment is ready.
- [ ] Run `make test` only if pytest and the local test environment are installed.
- [ ] Treat data pipeline checks as research release evidence, not as static Vercel frontend blockers when the public frontend data file already exists and the Next.js build passes.

## Optional Future QA

- [ ] Density Playwright QA is not currently configured; add it in a future testing pass before treating `qa:density-ui` as a blocker.

## Public Routes

- [ ] `/` renders the source-grounded map index for records with public display locations.
- [ ] `/map` renders the same map view as a route alias.
- [ ] `/dashboard` renders.
- [ ] `/density` renders density views.
- [ ] `/source` renders the source register.
- [ ] `/about` renders scope, methods, source policy, mapping limits, and ethics.
- [ ] `/topics` and `/topics/*` render research-safe search topic entry points.
