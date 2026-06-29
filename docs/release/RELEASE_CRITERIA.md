# First Public Release Criteria

This document defines what "first public release" means for the Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters.

The release thresholds are corpus readiness thresholds only. They are not truth claims about real-world phenomenon frequency, prevalence, or distribution.

## Corpus Thresholds

Preferred launch standard:

- At least 3500 public records.
- At least 1200 mapped records.

Documented fallback standard:

- At least 3200 public records.
- At least 1100 mapped records.
- Any fallback release must explain why the preferred threshold is not required for the domain launch.

## Required Release Conditions

- Public records meet the current source policy.
- Map flags meet the current map eligibility policy.
- `mapped_record_count == map_points.length == map_flags.length`.
- `npm ci` passes.
- `npm run typecheck` passes.
- `npm run build` passes.
- `python3 scripts/check_vercel_release.py` passes.
- `make audit-v2` and `make validate-v2` pass when the local Python/data environment is ready, or documented non-release-blocking warnings are accepted.
- There is no known severe UI breakage on the public routes.
- Restricted, suppressed, rejected, or scope-excluded records do not appear in `public/data/frontend-data.json`.
- README describes the current title, scope, limits, citation, and licensing.
- Licensing is clear: MIT infrastructure code, custom visual-interface license, and third-party rights retained.
- Production domain `https://ausfigures.com` works over HTTPS.
- Domain binding and `www` to apex redirect are verified.
- Basic mobile and small-screen usability has been checked.

## Current Local Baseline

The generated baseline files are authoritative for the current checkout:

- `data/processed/v2/release_baseline.md`
- `data/processed/v2/release_baseline.json`
- `data/processed/v2/release_validation_report.md`
- `data/processed/v2/release_readiness_report.md`

As of the current generated baseline, the public export exceeds the preferred corpus thresholds.
