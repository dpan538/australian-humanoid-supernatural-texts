# HSS Paper Preparation

Working title: "Discovery is not evidence: a source-chain model for unstable public-text archives"

This folder prepares repository evidence for a Humanities and Social Sciences Communications research Article. The paper uses the Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters as a methodological case study in provenance-aware digital archiving. It does not argue that supernatural claims are true.

## Scope

The paper corpus is a reproducible snapshot of local data products, not a new public release and not a redesign of the website. Public website display counts, local frontend export counts, legacy flat-record counts, V2 normalized counts, strict-record experiment counts, lead-mode counts, and mapped-record counts are separate units unless generated provenance tables explicitly connect them.

## Generated Files

Run the paper targets from the repository root:

```sh
make paper-freeze
make paper-stats
make paper-figures
make paper-audit-sample
make paper-check
```

Generated aggregate outputs are written under `data/releases/paper_hss_discovery_not_evidence_20260706/`. The scripts do not copy raw source text, HTML, PDFs, Word files, credentials, cookies, or the SQLite database into the release directory.

## Manuscript Use

Use `COUNT_RECONCILIATION.md` for citable count definitions, `CORPUS_SNAPSHOT.md` for the local paper freeze, `REPRODUCIBILITY.md` for commands, `DATA_SAFETY_AND_REDACTION.md` for public-sample rules, and `FIGURE_TABLE_INVENTORY.md` for generated assets.
