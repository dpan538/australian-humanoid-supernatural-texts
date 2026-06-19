# Public Collection Round 002 Plan

Run id: `public_round_002`
Created at: `2026-06-19T10:52:56+00:00`
Mode: plan only; no network requests; no records inserted.

## Execution Context

- Script: `scripts/collect_public_round_002.py`
- Config: `/Users/jarlgiovanni/Desktop/bigfoot_research/config/round_002.yml`
- Noise rules: `/Users/jarlgiovanni/Desktop/bigfoot_research/config/noise_rules.yml`
- DB path: `/Users/jarlgiovanni/Desktop/bigfoot_research/data/processed/australian_humanoid_figures.sqlite`
- Leads output: `/Users/jarlgiovanni/Desktop/bigfoot_research/data/interim/public_round_002_leads.csv`
- Location output: `/Users/jarlgiovanni/Desktop/bigfoot_research/data/interim/public_round_002_location_review.csv`
- Report output: `/Users/jarlgiovanni/Desktop/bigfoot_research/data/processed/public_round_002_plan.md`
- Validation queue included: `True`
- Keep blocked rows: `False`
- Limit: `None`
- Sample: `None`
- Output suffix: ``

## Purpose

Prepare a broader but still conservative public-source collection round before live fetching starts.
The plan prioritises earlier source discovery, public metadata review, and explicit location-evidence tracking.

## Safety Gates

- Australia-only scope.
- Public, published, openly discoverable sources only.
- No restricted, secret/sacred, unpublished, community-controlled, or non-public materials.
- Public catalogue metadata is treated as a lead, not permission to extract restricted cultural knowledge.
- Validation-queue terms are written as validation leads only and are not promoted to `include_v1`.
- High-noise bare queries and non-public source rows are blocked by the plan validator.

## Lead Counts

- Candidate lead rows before filtering: 486
- Written lead rows: 456
- Filtered or blocked rows: 0
- Duplicate query/source/date rows merged: 30
- Duplicate lead IDs detected: 0

### By action

- `planned_public_query`: 264
- `validation_queue_only`: 192

### By source type

- `aiatsis_public_catalogue`: 60
- `andc`: 48
- `modern_web`: 24
- `nla_catalogue`: 72
- `trove_magazine`: 108
- `trove_newspaper`: 144

### By date band

- `backsearch_negative_control`: 48
- `early_anchor`: 96
- `modern_yowie_heritage_tourism_media`: 204
- `publication_expansion`: 108

### By execution priority

- `1`: 192
- `2`: 12
- `3`: 34
- `4`: 77
- `5`: 141

### Non-Blocking Review Guards

- `MANUAL_REVIEW_RECOMMENDED`: 44

## Blocked Row Sample

- None

## Figures Without Planned Queries

- None

## Duplicate Lead IDs

- None

## Location Review

- Records in location queue: 208
- Records needing location review: 8

Location fields are evidence fields, not final geocoding truth. The `locations_json` column preserves per-place evidence, confidence, type, and notes for review.

## Outputs

- `/Users/jarlgiovanni/Desktop/bigfoot_research/data/interim/public_round_002_leads.csv`
- `/Users/jarlgiovanni/Desktop/bigfoot_research/data/interim/public_round_002_location_review.csv`
- `/Users/jarlgiovanni/Desktop/bigfoot_research/data/interim/public_round_002_metadata.json`
- `/Users/jarlgiovanni/Desktop/bigfoot_research/data/interim/public_round_002_manifest.json`

## Next Live-Collection Step

After reviewing this plan, implement source-specific collectors one at a time. Start with manual Trove/NLA metadata verification, then add API-backed retrieval only where credentials, publicness, and rate limits are clear.
