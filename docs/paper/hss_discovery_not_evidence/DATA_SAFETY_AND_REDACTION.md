# Data Safety And Redaction

The paper package reports aggregate archive-method statistics and a redacted audit sample. It must not publish raw copyrighted source text, restricted material, private notes, credentials, cookies, API keys, or sensitive Aboriginal and Torres Strait Islander material.

## Release Boundary

The paper release may contain:

- aggregate CSV/JSON tables;
- generated Markdown summaries;
- simple SVG figures derived from aggregate tables;
- redacted manual-audit samples with metadata only.

The paper release must not contain:

- copied SQLite databases;
- raw text, HTML, XML, PDFs, or Word documents;
- snippets, descriptions, summaries, full-text paths, raw metadata JSON, cookies, or credentials;
- sensitive Indigenous-related rows in public samples.

## Manual Audit Sample

`generate_audit_sample.py` samples from lead metadata with a deterministic random seed. It excludes sensitive-looking rows by default and outputs URL domains rather than full URLs. Human coding columns are blank so reviewers can code eligibility without receiving raw source content.

Required human coding columns:

- `source_chain_complete`
- `original_source_identifiable`
- `evidence_source_adequate`
- `date_available`
- `term_available`
- `source_stated_place_available`
- `ethics_sensitive`
- `record_eligible`
- `map_eligible`
- `reason_not_eligible`
- `reviewer_notes`

## Validation

`make paper-check` scans generated paper outputs for secret-like strings, forbidden copied file types, sensitive-looking public sample rows, and count drift between Markdown and JSON/CSV stats.
