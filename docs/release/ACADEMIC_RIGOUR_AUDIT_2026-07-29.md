# Academic Rigour Audit — 2026-07-29

## Decision

**PASS — eligible for release**

This audit covers every public data record, every registered source, the record-to-source relationships, ethics/indexing policy, mapped-record equivalence, and the generated production build. It evaluates provenance and publication controls; it does not validate the truth of supernatural claims.

## Scope

- Data export generated: `2026-07-06T12:19:52+00:00`
- Records audited: **4,265**
- Registered sources audited: **54**
- Discovery queries cross-checked: **328**
- Map points / display flags audited: **1,593 / 1,593**
- Page-eligible / index-eligible / review-only pages: **4,263 / 3,706 / 557**

## Release checks

| Result | Check | Evidence |
|---|---|---|
| PASS | Published record count equals the data array | summary=4265; records=4265 |
| PASS | Registered source count equals the source array | summary=54; sources=54 |
| PASS | Mapped count, map points, and map flags remain one coherent layer | summary_mapped=1593; points=1593; flags=1593 |
| PASS | Every record identifier is unique | 0 duplicated identifiers |
| PASS | Every source identifier is unique | 0 duplicated identifiers |
| PASS | Every record resolves to a registered source | 0 broken links |
| PASS | Record source names and types match the registry | 0 mismatches |
| PASS | Every record has the minimum provenance and classification fields | 0 incomplete records |
| PASS | Every record has a public HTTP(S) source URL | 0 invalid or local URLs |
| PASS | Every registered source has method, publicness, and ethics metadata | 0 incomplete sources |
| PASS | All declared source base URLs are public HTTP(S) URLs | 0 invalid source URLs |
| PASS | Restricted, suppressed, rejected, and explicitly excluded rows are absent from the public record layer | 0 prohibited rows |
| PASS | Each mapped record produces one display flag | 0 duplicated mapped record identifiers |
| PASS | Every map point and flag resolves to a public data record | 0 orphan flags; 0 orphan points |
| PASS | Strict map points, map points, and display flags contain the same record identifiers | 0 identifier mismatches |
| PASS | Every page-eligible record has a generated HTML page | 0 missing record pages |
| PASS | Every index-eligible record is present in the sitemap | 0 missing sitemap routes |
| PASS | Review-only record pages are absent from the sitemap | 0 review routes in sitemap |
| PASS | Every review-only record page declares noindex | 0 review pages missing noindex |
| PASS | Index-eligible record pages do not declare noindex | 0 index pages with noindex |
| PASS | Every generated record page retains its original public source URL | 0 pages without the source URL |
| PASS | Control and excluded records are absent from the sitemap | 0 excluded routes in sitemap |

## Required scholarly disclosures

| Disclosure | Current evidence |
|---|---|
| Review-only records remain crawlable for inspection but excluded from search indexing | 557 pages use noindex; 412 explicitly await human review and 146 carry caution flags. |
| Missing author metadata | 4192 records lack a named author and must be cited by title/source rather than supplied with an invented attribution. |
| Shared source URLs | 369 source URLs support 3089 records. This is expected for books, indexes, and multi-record archive pages; record identity must not be inferred from URL uniqueness. |
| Source concentration | Internet Archive: 1,536 (36.01%); Australian Yowie Research: 1,010 (23.68%); Project Gutenberg: 499 (11.70%); Australian Yowie Research / AYR Yowie Reports Map: 350 (8.21%); Project Gutenberg Australia: 192 (4.50%) |
| Registered discovery sources versus record-bearing sources | 45 of 54 registered sources currently contribute records; 9 are query/discovery or reserved registry entries. |
| Sources without one fixed base endpoint | 2 registry entries omit base_url; their records still carry direct public URLs and are checked individually. |

Missing authors are not inferred. Shared URLs are not deduplicated automatically because a book, archive index, or source page may support several separately coded public records. Source concentration and incomplete mapping are properties of the archive corpus, not estimates of real-world incidence.

## Ethics and review distribution

| Ethics flag | Records | Corpus share |
|---|---:|---:|
| public_context_reviewed | 2,009 | 47.10% |
| ok_public | 1,043 | 24.45% |
| needs_human_review_before_production_import | 371 | 8.70% |
| public_fiction_reviewed | 358 | 8.39% |
| public_media_context_reviewed | 118 | 2.77% |
| caution_indigenous_related_public_retelling | 77 | 1.81% |
| caution_indigenous_knowledge | 69 | 1.62% |
| public_ethnographic_text_reviewed | 50 | 1.17% |
| needs_human_ethics_review | 41 | 0.96% |
| public_metadata_context_reviewed | 39 | 0.91% |
| public_institutional_history_reviewed | 35 | 0.82% |
| public_page_context_reviewed | 19 | 0.45% |
| public_local_history_reviewed | 14 | 0.33% |
| public_institutional_or_media_context_reviewed | 8 | 0.19% |
| public_media_context_summary_only | 4 | 0.09% |
| public_abc_media_source_reviewed_summary_only | 2 | 0.05% |
| public_education_context_summary_only | 2 | 0.05% |
| public_institutional_newsletter_reviewed | 2 | 0.05% |
| public_memoir_reviewed | 2 | 0.05% |
| public_abc_education_source_reviewed_summary_only | 1 | 0.02% |
| public_media_and_local_history_reviewed | 1 | 0.02% |

Only `ok_public` and `public_*` records are search-index eligible. Caution and pending-review records remain inspectable as source-grounded archive rows but are excluded from the sitemap and carry `noindex`.

## Complete source-register audit

| ID | Source | Type | Records | Queries | Endpoint basis | Metadata |
|---:|---|---|---:|---:|---|---|
| 36 | Internet Archive | repository_full_text | 1,536 | 0 | declared | PASS |
| 12 | Australian Yowie Research | modern_web | 1,010 | 0 | declared | PASS |
| 38 | Project Gutenberg | public_domain_ebook | 499 | 0 | declared | PASS |
| 50 | Australian Yowie Research / AYR Yowie Reports Map | public_web_yowie_report_map | 350 | 0 | declared | PASS |
| 37 | Project Gutenberg Australia | public_domain_ebook | 192 | 0 | declared | PASS |
| 42 | Australian Broadcasting Corporation | institutional_media_page | 150 | 0 | declared | PASS |
| 35 | Wikisource | public_domain_transcribed_book | 108 | 0 | declared | PASS |
| 34 | Internet Sacred Text Archive | public_domain_transcribed_book | 65 | 0 | declared | PASS |
| 13 | OpenAlex | academic_metadata | 56 | 0 | declared | PASS |
| 31 | Project Gutenberg Australia | project_gutenberg_australia_book | 47 | 0 | declared | PASS |
| 15 | Internet Archive | internet_archive_metadata | 36 | 0 | declared | PASS |
| 52 | Open Library Search API | public_books_metadata_openlibrary | 33 | 0 | declared | PASS |
| 39 | Internet Archive | repository_full_text_article | 32 | 0 | declared | PASS |
| 40 | State Library Victoria | institutional_history_article | 21 | 0 | declared | PASS |
| 51 | Australian Yowie Research state report indexes | public_web_yowie_state_report_index | 21 | 0 | declared | PASS |
| 32 | Internet Sacred Text Archive | internet_sacred_texts_public_domain_book | 20 | 0 | declared | PASS |
| 14 | Crossref | academic_metadata | 11 | 0 | declared | PASS |
| 33 | Wikisource | wikisource_public_domain_book | 10 | 0 | declared | PASS |
| 47 | National Trust and ABC public pages | institutional_history_and_media_pages | 8 | 0 | declared | PASS |
| 10 | English Wikipedia | modern_web | 6 | 0 | declared | PASS |
| 48 | National Trust of Australia (NSW) | institutional_history_article | 6 | 0 | declared | PASS |
| 54 | Internet Archive Advanced Search | public_books_metadata_internet_archive | 6 | 0 | declared | PASS |
| 41 | Adelaide Arcade | institutional_history_page | 5 | 0 | declared | PASS |
| 53 | Wikidata | public_wikidata_entity_metadata | 5 | 0 | declared | PASS |
| 25 | Australian Screen | institutional_web | 4 | 0 | declared | PASS |
| 26 | Adelaide Gaol | institutional_web | 4 | 0 | declared | PASS |
| 43 | Territory Stories | public_repository_ocr_text | 3 | 0 | declared | PASS |
| 23 | Port Arthur Historic Site | institutional_web | 2 | 0 | declared | PASS |
| 27 | National Trust Tasmania | institutional_web | 2 | 0 | declared | PASS |
| 44 | Territory Stories | public_repository_newsletter_ocr_text | 2 | 0 | declared | PASS |
| 11 | ABC News | modern_web | 1 | 0 | declared | PASS |
| 16 | Parks Victoria | institutional_web | 1 | 0 | declared | PASS |
| 17 | Old Melbourne Gaol | institutional_web | 1 | 0 | declared | PASS |
| 18 | Fremantle Prison | institutional_web | 1 | 0 | declared | PASS |
| 19 | Gunaikurnai Land and Waters Aboriginal Corporation | community_controlled_public_web | 1 | 0 | declared | PASS |
| 20 | Art Gallery of South Australia | institutional_web | 1 | 0 | declared | PASS |
| 21 | ACMI | institutional_web | 1 | 0 | declared | PASS |
| 22 | Australian National University | institutional_web | 1 | 0 | declared | PASS |
| 24 | Art Gallery of New South Wales | institutional_web | 1 | 0 | declared | PASS |
| 28 | National Trust Victoria | institutional_web | 1 | 0 | declared | PASS |
| 29 | J Ward Ararat | seeded_public_web | 1 | 0 | declared | PASS |
| 30 | Marriner Group | institutional_web | 1 | 0 | declared | PASS |
| 45 | Australian Screen Online | institutional_media_page | 1 | 0 | declared | PASS |
| 46 | Town of Gawler Council | municipal_local_history_pdf | 1 | 0 | declared | PASS |
| 49 | Australian Broadcasting Corporation | institutional_education_page | 1 | 0 | declared | PASS |
| 1 | Trove Newspapers and Gazettes | trove_newspaper | 0 | 105 | declared | PASS |
| 2 | Trove Magazines and Newsletters | trove_magazine | 0 | 105 | declared | PASS |
| 3 | National Library of Australia Catalogue | nla_catalogue | 0 | 27 | declared | PASS |
| 4 | AIATSIS Public Catalogue | aiatsis_public_catalogue | 0 | 27 | declared | PASS |
| 5 | Research Data Australia | andc | 0 | 27 | declared | PASS |
| 6 | Google Trends | google_trends | 0 | 5 | declared | PASS |
| 7 | Wikimedia Pageviews | wikimedia_pageviews | 0 | 5 | declared | PASS |
| 8 | Modern Public Web | modern_web | 0 | 27 | record-level URLs | PASS |
| 9 | Manual Import | manual | 0 | 0 | record-level URLs | PASS |

## Citation rule

Cite AusFigures for the aggregation, coding, interface, and public export. For a claim about one record, also cite the original public source linked on that record page. Do not cite AusFigures as evidence that a reported supernatural event occurred.

## Machine-readable evidence

The complete audit, all audited record identifiers, source-register results, source concentration, ethics distribution, build evidence, disclosures, and blocker list are stored in:

`data/processed/v2/academic_rigour_audit_2026-07-29.json`
