# Vercel Deployment

This note records the production settings for the AusFigures public interface.

## Production Target

- Production domain: `https://ausfigures.com`
- Canonical route: `/`
- Apex domain policy: `https://ausfigures.com` is canonical.
- Preview policy: `*.vercel.app` URLs are preview deployments only and must not be used in production metadata, sitemap, robots, llms.txt, or README deployment badges.

## Runtime

- Framework: Next.js
- Node.js: `22.x` as declared in `package.json`.
- Package manager: npm with committed `package-lock.json`.
- Install command: `npm ci`.
- Build command: `npm run build`.
- Output directory: leave unset in Vercel. The project uses the Next.js framework preset and lets Vercel detect `.next`.
- Required production environment variables: none currently known.
- Public data dependency: `public/data/frontend-data.json` must exist before build.

## Pre-Deploy Checks

Run these once, in order:

```sh
npm ci
npm run typecheck
npm run build
python3 scripts/check_vercel_release.py
```

`make export-frontend`, `make audit-v2`, `make validate-v2`, and `make test` are data pipeline or research release checks, not hard blockers for a static Vercel frontend when `public/data/frontend-data.json` already exists and the frontend build passes. Run them with timeouts only when the local Python/data environment is ready.

## Vercel Project Settings

- Framework Preset: `Next.js`.
- Root Directory: repository root.
- Production Branch: `main`.
- Install Command: `npm ci`.
- Build Command: `npm run build`.
- Output Directory: leave blank/default for the Next.js preset.
- Environment Variables: none required for the static public frontend.

## Domain

- Canonical domain: `https://ausfigures.com`.
- Add `ausfigures.com` to the Vercel project.
- Add `www.ausfigures.com` if using the www redirect.
- Redirect `https://www.ausfigures.com/*` to `https://ausfigures.com/*`.
- Configure DNS records exactly as Vercel shows in Project Settings -> Domains or via `vercel domains inspect`.
- Wait for DNS verification and SSL provisioning.

## SEO Checks

- `metadataBase` uses `https://ausfigures.com`.
- Canonical route metadata uses `https://ausfigures.com`.
- Root route metadata titles the homepage as the AusFigures map index.
- Research topic entry points use source-grounded discovery language for Australian supernatural, Yowie, bunyip, ghost, apparition, and spirit-person searches.
- Open Graph and Twitter metadata use `summary_large_image` framing and canonical `ausfigures.com` image URLs.
- Browser identity metadata includes `/manifest.webmanifest`, `/apple-icon`, theme colors, and Safari/Chrome app titles.
- `www.ausfigures.com/*` redirects permanently to `https://ausfigures.com/*`.
- Sitemap only lists `https://ausfigures.com` URLs.
- Robots references `https://ausfigures.com/sitemap.xml`.
- `llms.txt` uses canonical apex URLs.
- `llms-full.txt` provides expanded public-safe AI/search context.
- Dataset JSON-LD uses a license URL, `Place` spatial coverage, and the public frontend data distribution URL.
- No production metadata or public discovery file points to a `*.vercel.app` URL.

## Post-Deploy Smoke Checks

Check these paths on the production deployment:

- `/` returns 200 and renders the index map.
- `/map` returns 200 as a map route alias.
- `/dashboard` returns 200.
- `/density` returns 200.
- `/source` returns 200.
- `/about` returns 200.
- `/topics` returns 200.
- `/topics/australian-supernatural` returns 200.
- `/robots.txt` returns 200 and references `https://ausfigures.com/sitemap.xml`.
- `/sitemap.xml` returns 200 and only lists canonical public routes.
- `/llms.txt` returns 200 and contains only public launch guidance.
- `/llms-full.txt` returns 200 and contains only public AI/search guidance.
- `/opengraph-image` returns 200 image/png and uses research-safe framing.
- `/twitter-image` returns 200 image/png and uses research-safe framing.
- `/manifest.webmanifest` returns 200 application/manifest+json or compatible JSON.
- `/apple-icon` returns 200 image/png.
- `/data/frontend-data.json` returns 200.

## Security Headers

`next.config.ts` sets:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

Strict CSP is intentionally deferred because the app uses an inline theme bootstrap script.
