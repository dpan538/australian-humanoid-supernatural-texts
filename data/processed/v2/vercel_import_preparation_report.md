# Vercel Import Preparation Report

Generated: `2026-06-28`

## Local State

- Branch: `codex/map-dot-bug-fix`
- Base commit before this preparation: `37046d344e61abb7f74448de348f6b0bfc77c4a1`
- `origin/main` before this preparation: `37046d344e61abb7f74448de348f6b0bfc77c4a1`
- Domain target: `ausfigures.com`
- Node version observed locally: `v22.21.0`
- Package manager: `npm` with `package-lock.json`
- Next.js dependency: `^16.0.0`
- Production build command: `npm run build`

Unrelated local worktree noise remains present and was not staged: raw/interim
data, crawler/cache outputs, local generated reports, local database files, and
document artifacts.

## Static Data Baseline

- Public records: `3809`
- Mapped records: `1206`
- `map_flags.length`: `1206`
- `map_points.length`: `1206`
- Map invariant: pass
- Source rows: `49`
- Frontend JSON size: `20717839` bytes
- Static runtime data path: `/data/frontend-data.json`
- Runtime SQLite dependency: none for the public frontend

## Vercel Readiness

- Added minimal `vercel.json`.
- Added `.vercelignore` to keep raw/interim/database workbench files out of deploy uploads.
- Added `scripts/check_vercel_release.py`.
- Added Vercel first-import checklist.
- Added `ausfigures.com` domain setup notes.
- Updated Next metadata for `AusFigures | Public Text Archive`.
- No environment variables are required by the current build.
- Vercel CLI was not available locally; first deployment is expected through Vercel Git import.

## Theme And Signal Controls

- Added `MODE DARK/LIGHT`.
- Kept `SIGNAL NORMAL/HIGH`.
- Moved controls onto the same footer baseline as route navigation.
- Preferences persist in `localStorage`.
- Root attributes applied:
  - `data-theme="dark|light"`
  - `data-signal-gain="normal|high"`
- Fixed preference hydration so route changes and reloads do not overwrite saved choices.
- Light mode uses an archival paper / technical print palette rather than a plain white SaaS palette.

## Motion Budget

- Added `frontend_motion_audit.md`.
- Added `frontend_motion_audit.json`.
- Map reveal remains chronological quantity accumulation.
- Map markers do not grow, fade, glow, or loop continuously.
- Source and About ambient motion remains limited to small non-text status elements.
- Dashboard animation remains finite and interaction/data-reveal scoped.

## QA Results

- `python3 scripts/check_vercel_release.py`: pass
- `python3 scripts/validate_v2.py`: pass, `13` checks and `0` failed
- `python3 scripts/run_tests.py`: pass
- `npm run build`: pass
- Local route smoke tests: `/about`, `/map`, `/dashboard`, `/density`, `/source` all returned successfully
- Browser QA: no page console warnings/errors reported
- Map browser count: `1206` markers, `1206` visible after reveal
- Theme/signal persistence: pass after reload for all four tested combinations

## Screenshot Evidence

- `/map` dark normal: `data/processed/v2/vercel_theme_qa_screenshots/map_dark_normal.png`
- `/map` dark high: `data/processed/v2/vercel_theme_qa_screenshots/map_dark_high.png`
- `/map` light normal: `data/processed/v2/vercel_theme_qa_screenshots/map_light_normal.png`
- `/map` light high: `data/processed/v2/vercel_theme_qa_screenshots/map_light_high.png`
- `/about` dark normal: `data/processed/v2/vercel_theme_qa_screenshots/about_dark_normal.png`
- `/about` dark high: `data/processed/v2/vercel_theme_qa_screenshots/about_dark_high.png`
- `/about` light normal: `data/processed/v2/vercel_theme_qa_screenshots/about_light_normal.png`
- `/about` light high: `data/processed/v2/vercel_theme_qa_screenshots/about_light_high.png`

Screenshots are local QA artifacts and are not required for deployment.

## Known Limitations

- No Open Graph image was added in this task.
- Vercel CLI was not installed, so `vercel pull --yes` and `vercel build` were not run locally.
- DNS values are intentionally not hard-coded; the Vercel UI should be treated as the source of truth after adding the domain.

## Next Manual Steps

1. Confirm GitHub `main` has this commit.
2. In Vercel, import `dpan538/australian-humanoid-supernatural-texts`.
3. Use project name `ausfigures`.
4. Confirm Next.js preset, root directory `./`, install command `npm install`, build command `npm run build`, output `.next`.
5. Deploy and test the temporary Vercel URL.
6. Add `ausfigures.com` and `www.ausfigures.com`.
7. In Namecheap, copy exactly the DNS records shown by Vercel.
8. Confirm HTTPS and canonical redirect.
