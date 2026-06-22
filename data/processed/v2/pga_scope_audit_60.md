# Project Gutenberg Australia Scope Audit: 60 Section-Level Records

- Generated: `2026-06-22T04:10:47+00:00`
- Records reviewed: `60`
- Audit CSV: `data/exports/v2/pga_scope_audit_60.csv`

## Summary

- Retained first-class records: `12`
- Retained context records: `35`
- Excluded records: `13`
- Corrected source labels: `46`
- Narrative-type changes: `26`

## Eligibility Decisions

| decision | records |
|---|---:|
| core_supernatural_humanoid_narrative | 12 |
| humanoid_adjacent_context | 17 |
| traditional_context_only | 18 |
| non_humanoid_narrative | 12 |
| insufficient_evidence | 0 |
| exclude_from_public_corpus | 1 |

## Correction Policy Applied

- `title` was normalized to the section/story title, without the parenthetical book suffix.
- `source_label` was moved away from section titles and into actual source-used names or controlled descriptors.
- First-class retained rows require a focal supernatural, anomalous, spirit-person, giant/ogre-person, apparition, or otherwise nonordinary person-form agent.
- Animal-origin, plant-origin, flood, solar, celestial, and cosmological stories were not treated as core merely because human communities or ordinary people appear.
- `non_humanoid_narrative` and `exclude_from_public_corpus` rows are retained in SQLite for audit but marked `scope_excluded`/`suppressed` for public export counts.
- `humanoid_adjacent_context` and `traditional_context_only` rows remain retained context records with `summary_only` display semantics.

## Narrative-Type Changes

| from | to | records |
|---|---|---:|
| giant_or_ogre_narrative | spirit_person_narrative | 2 |
| giant_or_ogre_narrative | traditional_narrative | 3 |
| spirit_person_narrative | descriptive_belief_record | 1 |
| spirit_person_narrative | traditional_narrative | 4 |
| traditional_narrative | descriptive_belief_record | 2 |
| traditional_narrative | giant_or_ogre_narrative | 1 |
| traditional_narrative | spirit_person_narrative | 13 |

## Notes

Distinctness was not re-litigated here; this audit only reviewed project-scope eligibility and field semantics. The row-level decisions are in the CSV.
