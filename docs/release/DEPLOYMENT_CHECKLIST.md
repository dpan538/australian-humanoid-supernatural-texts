# Deployment Checklist

## Pre-Deploy

- `git status --short --branch` is clean except intentional release files.
- `python3 scripts/export_frontend_json.py` has been run.
- `python3 scripts/validate_v2.py` has been run.
- `python3 scripts/validate_release.py` passes.
- `python3 scripts/run_tests.py` passes.
- `npm run build` passes.
- README is updated.
- Release notes are ready.
- Domain is selected.
- Environment variables are reviewed.
- No secrets are committed.
- No raw/interim/crawler noise is staged.

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
- Confirm production URL.
- Confirm `/data/frontend-data.json` loads.
- Confirm `/about`, `/map`, `/dashboard`, `/density`, and `/source`.
- Confirm map marker count.
- Confirm custom domain binding.
- Confirm HTTPS.
- Confirm redirect from `www` to apex or apex to `www`.

## Post-Deploy

- Smoke test all pages.
- Run mobile small-screen checks.
- Confirm source/ethics disclaimer is visible.
- Check GitHub repository description and topics.
- Create GitHub release tag.
- Archive the release baseline and readiness report.

