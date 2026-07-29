# Major Phase Report: Collection Expansion, Lead Intelligence, Release Layers, and Site Integration

Generated: `2026-07-06T15:45:59+00:00`

## 1. Executive Summary

This phase moved AusFigures from strict no-credential target-record recovery into a provenance-aware release architecture. Strict target-record mode found no eligible target-gap records under the active constraints, so the project preserved the work as labelled metadata-only and research-lead layers rather than weakening public-record gates.

The final site release keeps accepted public records, accepted public map points, metadata-only gap items, research leads, source intelligence, redirects, and frontend sidecars as separate layers. This makes the 1926-2011 coverage legible without claiming that lower-evidence rows are accepted records.

## 2. Timeline of Phases

| Phase | Outcome |
| --- | --- |
| Collection Expansion V2 | Established canonical schema, public export, source-chain and map evidence checks. |
| No-auth autoharvest | Explored public, no-login/no-key surfaces without public mutation. |
| Gap-targeted marathon | Focused on 1926-1976 and priority jurisdictions. |
| Target acquisition recovery | Tested whether strict target records could be recovered from near misses. |
| Structured endpoint recovery | Audited and enriched no-key structured endpoints. |
| Near-miss rescue | Materialised near misses and attempted robots-aware enrichment. |
| Strict closeout | Closed no-credential strict-record mode at 0 target-gap records. |
| Lead intelligence | Converted useful blocked material into target-gap leads. |
| Research-volume expansion | Added 25,000 research-layer items without public promotion. |
| Final release sprint | Froze inputs, built release layers, redirects, map overlays, and package sidecars. |
| Site integration and rebuild | Built count contract, cards, charts, frontend wiring, smoke tests, and final audit. |

## 3. Data-Layer Architecture

| Layer | Public meaning | Release handling |
| --- | --- | --- |
| Accepted public records | Existing accepted archive records | Displayed as public records only. |
| Accepted public map | Existing verified map points | Default map layer only. |
| Metadata-only gap items | Catalogue/citation/metadata coverage | Labelled not accepted public records. |
| Research lead overlay | Useful source-chain or target-gap leads | Labelled research leads requiring review. |
| Source intelligence | Route/source/blocker analytics | Decision support, not evidence. |
| Redirects | Canonical ID/URL resolution | Route/data resolution, not evidence replacement. |
| Frontend sidecars | Release package data | Loaded separately from accepted frontend data. |
| Count contract | Single count source | Used by pages, cards, charts, and audits. |

## 4. Key Counts

| Metric | Count |
| --- | ---: |
| Accepted public map count | 1,593 |
| Metadata overlay | 1,552 |
| Lead overlay | 1,448 |
| 1926-2011 coverage items | 37,964 |
| Critical hard gaps | 0 |
| Display hard gaps | 0 |
| Internal patch items | 3,000 |
| ID redirects | 8,697 |
| URL redirects | 9,876 |
| Total leads before dedupe | 11,343 |
| Canonical/unique leads | 2,646 |
| Canonical priority leads | 207 |
| Metadata-only 1955-1976 leads | 551 |
| Research-volume expansion items | 25,000 |
| Expansion target-gap leads | 6,000 |
| Expansion metadata-only leads | 4,000 |
| Expansion auxiliary source-intelligence rows | 15,000 |
| Strict target-gap records found | 0 |
| Watchdog hard violations | 0 |

## 5. Methodological Findings

- Strict no-credential target-record mode produced 0 strict target-gap records under the active source universe and gates.
- Missing-date evidence dominated strict blockers; public metadata often supplied terms or route context without item-level date/term completeness.
- No-auth official surfaces produced useful leads but not strict records.
- Structured endpoint recovery was limited by robots uncertainty and detail-page access constraints.
- Metadata-only and lead layers are necessary for observational coverage, especially for 1955-1976 and priority states.
- The map must be read as a public display-location interface, not as proof, habitat, or population evidence.

## 6. Engineering Safeguards

- No public record autopromotion.
- No map flag autopromotion.
- Public artifact guard.
- Autoharvest watchdog.
- Redirect validation.
- Canonical count contract.
- Layer labels in frontend cards/charts/pages.
- Frontend smoke tests.
- Final release and post-release site audits.

## 7. Frontend Integration

- Existing accepted frontend data remains in `public/data/frontend-data.json`.
- Release sidecars are loaded separately through `lib/release-data.ts`.
- Map page keeps accepted public map as default and surfaces metadata/lead overlays as separate research layers.
- Density page exposes 1926-2011 multi-layer coverage with accepted, metadata-only, and lead layers separated.
- Source and About pages report release-layer counts without inflating accepted records.
- Cards and charts are generated into public sidecars with badges, caveats, provenance, and count-contract checks.
- Redirect sidecars are used as route-resolution data, not evidence-source replacement.

## 8. Known Limitations

- Accepted records still differ from metadata-only and lead coverage.
- Source concentration caveats remain for discovery/access-platform material.
- Missing-date evidence remains in some lead layers.
- Robots uncertainty blocks some detail pages.
- Culturally sensitive material remains held or manual-only.
- D-class access platforms still require original-source decomposition.

## 9. Use In Future Paper

This phase supports a paper about provenance-aware digital folklore archives, especially the difference between a record and a lead, the limits of metadata availability, automation constraints in no-credential collection, map/source-chain bias, and the infrastructure needed to make uncertainty visible rather than hidden.

## 10. Reproducibility

Key commands include `make release-sprint-all`, `make release-apply-package-dry-run`, `make release-apply-package`, and `make post-release-site-integration-all`. The principal outputs are the count contract, release cards, release charts, final site audit, smoke test report, and this report.

## 11. Final Release Status

Final go/no-go status: `ready`.

The site is release-ready when the post-release audit is PASS or WARN-only. Lower-evidence research layers remain useful for analysis but are not accepted public records.
