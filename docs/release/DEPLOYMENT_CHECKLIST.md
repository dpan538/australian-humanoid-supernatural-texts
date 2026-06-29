# Deployment Checklist

## Pre-Deploy

- `git status --short --branch` is clean except intentional release files.
- `public/data/frontend-data.json` exists and is intended public data.
- `npm ci` passes.
- `npm run typecheck` passes.
- `npm run build` passes.
- `python3 scripts/check_vercel_release.py` passes.
- `robots.txt`, `sitemap.xml`, and `llms.txt` are present and public-safe.
- README is updated.
- Release notes are ready.
- Canonical production domain is `https://ausfigures.com`.
- Environment variables are reviewed.
- No secrets are committed.
- No raw/interim/crawler noise is staged.

Data pipeline checks such as `make export-frontend`, `make audit-v2`, `make validate-v2`, and `make test` should be run when the local Python/data environment is ready, but they are not hard blockers for deploying the static Vercel frontend if the public data export already exists and the Next.js build passes.

## GitHub Metadata

Suggested description:

```text
Typed public-text archive and research display for Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings.
```

Suggested topics:

```text
digital-humanities, public-archive, folklore, australian-history, data-visualization, research-interface, supernatural-narratives, provenance
```

Do not use misleading topics such as `cryptid-proof`, `monster-database`, or `paranormal-evidence`.

If `gh` is available and authenticated, update metadata with:

```sh
gh repo edit dpan538/australian-humanoid-supernatural-texts \
  --description "Typed public-text archive and research display for Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings." \
  --add-topic digital-humanities,public-archive,folklore,australian-history,data-visualization,research-interface,supernatural-narratives,provenance
```

## Deploy

- Push `main`.
- Deploy on Vercel or the selected target host.
- Confirm production URL is `https://ausfigures.com`.
- Confirm `/dashboard` is the canonical public entry route.
- Confirm `/data/frontend-data.json` loads.
- Confirm `/about`, `/map`, `/dashboard`, `/density`, and `/source`.
- Confirm `/robots.txt`, `/sitemap.xml`, and `/llms.txt`.
- Confirm map marker count.
- Confirm `ausfigures.com` custom domain binding.
- Confirm HTTPS.
- Confirm redirect from `www.ausfigures.com` to apex.

## Post-Deploy

- Smoke test all pages.
- Run mobile small-screen checks.
- Confirm source/ethics disclaimer is visible.
- Check GitHub repository description and topics.
- Create GitHub release tag.
- Archive the release baseline and readiness report.
