# Tables Draft

## Table 1. Core terms and units of analysis

| term | draft definition | manuscript use |
| --- | --- | --- |
| public-text trace | A discoverable public metadata or text signal that may indicate a relevant source-chain path but has not necessarily satisfied record criteria. | Introduction; Data and methods |
| source-grounded narrative unit | The V2 top-level unit for a public narrative or source-grounded record. It is not equivalent to an asserted event. | Data and methods |
| candidate lead | A reviewable trace retained because one or more provenance, source, date, term, place, publicness, or ethics gates are incomplete. | Data and methods; Results |
| record | A source-grounded unit that satisfies the relevant provenance and review gates for the archive layer in which it appears. | Data and methods |
| provenance gate | A rule or review point that prevents discovery-only material from becoming a record without adequate source-chain support. | Data and methods; Discussion |
| source-stated place | A place relation grounded in a public source or public metadata field, rather than inferred from institutional custody or broad regional association. | Data and methods; Map results |
| display location | A controlled map display point for a public record, not a statement of truth, habitat, population, or occurrence. | Map policy; Discussion |
| archival visibility | The condition of being findable through search, catalogues, repositories, access platforms, or public web routes. | Introduction; Discussion |

## Table 2. Source-chain layers and evidentiary status

| source-chain layer | definition | evidentiary status | example metadata only |
| --- | --- | --- | --- |
| discovery_source | Route by which a candidate trace becomes visible, such as a search result, route registry, sitemap, aggregator, or catalogue query. | Discovery only unless independently supported. | Route family, query route, source registry entry. |
| access_source | Platform or interface through which material or metadata can be accessed. | Access mediation, not necessarily authorship or evidence. | Repository domain, digitization platform, catalogue interface. |
| original_source | Attributable publication, organization, authorial context, collection, or originating public text. | Attribution layer; may need confirmation. | Publication or organization name, original publication date where available. |
| evidence_source | Source item or metadata record adequate to support a source-grounded narrative unit under the archive's provenance gate. | Record-supporting layer when publicness, source, date/place/term, and ethics conditions are met. | Source item identifier, publicness status, evidence-source family. |

## Table 3. Blocker taxonomy

| blocker | generated count | generated share | interpretation |
| --- | ---: | ---: | --- |
| `missing_date` | 10,320 | 48.35% | Candidate trace lacks usable temporal signal for the configured gate. |
| `missing_item_url` | 6,000 | 28.11% | Route or directory is visible, but item-level evidence identity is absent. |
| `missing_term` | 3,863 | 18.1% | Candidate trace lacks controlled term signal under the configured rule. |
| `strict_record_gate_not_met` | 629 | 2.95% | Candidate has signals but still fails one or more record-gate requirements. |
| `ethics_sensitive` | 431 | 2.02% | Candidate requires sensitive-material handling rather than automated promotion. |
| `robots_unknown` | 100 | 0.47% | Automated enrichment is blocked by unclear robots or permission status. |

Source: `data/releases/paper_hss_discovery_not_evidence_20260706/tables/lead_blocker_counts.csv`.

## Table 4. Paper corpus snapshot

| count family | metric | generated value | source |
| --- | --- | ---: | --- |
| local frontend export | frontend records | 4,265 | `public/data/frontend-data.json` |
| local frontend export | frontend map points | 1,593 | `public/data/frontend-data.json` |
| local frontend export | frontend map flags | 1,593 | `public/data/frontend-data.json` |
| legacy flat corpus | records total | 4,638 | `records` table |
| V2 normalized corpus | source items total | 4,526 | `source_items` table |
| V2 normalized corpus | narrative units total | 4,457 | `narrative_units` table |
| V2 normalized corpus | public-display-eligible narrative units | 4,444 | `narrative_units` table |
| strict no-credential gate | strict target-gap records | 0 | `provisional_records` table |
| lead mode | target-gap leads | 21,343 | `target_gap_leads` table |
| priority leads | lead score >= 80 | 10,581 | `target_gap_leads` table |
| mapped public records | canonical frontend public map rows | 1,593 | `canonical_count_reconciliation.csv` |
| live public website display | live records and mapped records | not available in current local data | paper count reconciliation |

## Table 5. Manual audit examples

The following rows are metadata-only examples from the redacted audit sample. They are not human coding outcomes and do not include source text, snippets, descriptions, or full URLs.

| sample id | lead type | blocker | source family | route family | signal pattern | human coding status |
| --- | --- | --- | --- | --- | --- | --- |
| `audit_001` | `ROBOTS_BLOCKED_NEAR_MISS` | `robots_unknown` | `ATOM_AtoM` | `museum_heritage_page` | date present, term absent, place absent | pending |
| `audit_002` | `METADATA_ONLY_1955_1976_LEAD` | `missing_term` | `state_archive_catalogue` | `state_archive_catalogue` | date present, term absent, place present | pending |
| `audit_006` | `METADATA_ONLY_1955_1976_LEAD` | `strict_record_gate_not_met` | `museum_heritage_page` | `museum_heritage_page` | date present, term present, place present | pending |
| `audit_007` | `SOURCE_ATLAS_ROUTE_LEAD` | `missing_item_url` | `state_library_catalogue` | `state_library_catalogue` | date present, term present, place present | pending |
| `audit_020` | `STRUCTURED_ENDPOINT_ROUTE_LEAD` | `missing_date` | `OMEKA_API` | `local_history_serial` | date absent, term absent, place absent | pending |

Source: `data/releases/paper_hss_discovery_not_evidence_20260706/paper_manual_audit_sample.csv`.
