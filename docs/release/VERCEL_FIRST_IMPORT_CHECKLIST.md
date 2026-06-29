# Vercel First Import Checklist

## Before Import

- GitHub `main` contains the current frontend.
- `git status` has no uncommitted release/frontend files.
- `npm ci` works with `package-lock.json`.
- `python3 scripts/check_vercel_release.py` passes.
- `npm run build` passes.
- `public/data/frontend-data.json` is committed.
- `.vercelignore` exists.
- README has current project description.
- No `.env` secrets are required.
- No local absolute paths appear in frontend data.

## Vercel Import

- New Project -> Import Git Repository.
- Repository: `dpan538/australian-humanoid-supernatural-texts`.
- Project name: `ausfigures`.
- Framework Preset: `Next.js`.
- Root Directory: repository root.
- Install Command: `npm ci`.
- Build Command: `npm run build`.
- Output Directory: leave blank/default for the Next.js framework preset.
- Environment Variables: none unless a future build explicitly requires one.
- Deploy.

## After Import

- Open the temporary `*.vercel.app` URL as a preview deployment only.
- Test `/about`.
- Test `/map`.
- Test `/dashboard`.
- Test `/density`.
- Test `/source`.
- Confirm static data loads from `/data/frontend-data.json`.
- Confirm `/robots.txt`, `/sitemap.xml`, and `/llms.txt` load.
- Confirm map count matches local.
- Confirm Source and Dashboard counts match local.
- Confirm no console errors.

## Domain

- Add `ausfigures.com`.
- Add `www.ausfigures.com`.
- Configure Namecheap DNS using Vercel-provided records.
- Confirm Vercel domain status is valid.
- Confirm HTTPS.
- Confirm canonical redirect from `www` to apex.
- Confirm production metadata, sitemap, robots, llms.txt, and README use `https://ausfigures.com`, not the preview URL.
