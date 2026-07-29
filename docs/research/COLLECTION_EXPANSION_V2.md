# Collection Expansion V2

## Purpose

Collection Expansion V2 is a non-destructive framework for closing the 1926-1976 temporal gap, improving WA/SA/NT/TAS/ACT map balance, and separating discovery platforms from actual evidence sources. It stages candidate records for human review; it does not make staged candidates accepted public records.

## Route Strategy

The 1926-1954 route favours Trove newspaper and gazette metadata, state library catalogues, and local-history serials because newspapers and public catalogues are strongest for dated public attestations in that period.

The 1955-1976 route shifts toward state libraries, state archives, local studies, public broadcast catalogues, council local-history pages, and museum/heritage pages because post-1955 Trove coverage is patchier and rights/access conditions become more varied.

## Source Chain Model

- `discovery_source`: where a lead was found. Discovery-only sources cannot be accepted as evidence.
- `access_source`: the platform or catalogue that provides access, such as Internet Archive or PANDORA.
- `original_source`: the publication, collection item, broadcast, serial, or public record being mediated.
- `evidence_source`: the reviewed source that can support a public metadata record.

## Source Tiers

- `A`: Australian public archive, library, register, authority, or institution.
- `B`: local historical society, museum, council local-studies, or community public-history source.
- `C`: stable media, broadcast, or public broadcaster source.
- `D`: repository/access platform where the original source must be identified.
- `E`: discovery-only source.

## Map Eligibility

Map flags require source-stated place evidence, location role, coordinate evidence, review status, Australian jurisdiction, and no suppression decision. Publication location, archive custody location, institution address, author residence, state-only inference, and broad cultural region are not valid event/map points.

## Ethics

Aboriginal and Torres Strait Islander related material requires caution. Public metadata does not grant permission to reproduce, classify, map, or summarize culturally sensitive material. AIATSIS, AUSTLANG, oral history, and culturally sensitive collection routes default to manual review.

## Commands

```bash
make collection-expansion-migrate
make source-registry-sync
make plan-gap-queries
make probe-sources-dry-run
make audit-collection-balance
```

To inspect the importer without writing:

```bash
python3 scripts/import_reviewed_candidates_v2.py \
  --db data/processed/australian_humanoid_figures.sqlite \
  --review-csv data/review/v2/gap_probe_001_candidate_review.csv \
  --run-id reviewed_gap_import_001 \
  --dry-run
```

To import after review, use `--execute`.

## Candidate Review

Review CSVs are written to `data/review/v2/`. Human reviewers should fill evidence-source fields, original-source fields, ethics review status, display decision, and reviewer notes. Only rows with `review_status=accepted` are eligible for import.

Discovery-only rows require `accepted_evidence_source_name` and `accepted_evidence_source_url`. Sensitive or restricted rows require `display_decision=summary_only` or `display_decision=suppress_public`.

## Release Gates

`audit_collection_balance.py` writes release-gate results to `release_gate_results` and Markdown summaries in `data/processed/v2/`. `check_collection_release_gates.py` exits nonzero on `FAIL` and prints `WARN` gates for reviewer attention.

## What Not To Do

- Do not bypass paywalls, logins, robots.txt, access controls, cultural restrictions, rate limits, or terms.
- Do not mass-download copyrighted full text.
- Do not use Trove bulk harvest by default.
- Do not treat tourism pages, generic blogs, search pages, Wikipedia, or paranormal aggregators as evidence without a stronger public source.
- Do not infer map points from publication place, archive custody, institution address, author residence, state-only text, or broad cultural regions.
