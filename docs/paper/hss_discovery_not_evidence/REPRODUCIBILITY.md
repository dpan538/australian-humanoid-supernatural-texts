# Reproducibility

This paper package is intentionally read-only against the existing archive data. It derives aggregate CSV, JSON, Markdown, and SVG outputs from configured local inputs.

## Configuration

The active paper configuration is:

```text
config/paper_hss_freeze.yaml
```

The configuration records the working title, double-anonymous mode, local data paths, paper release directory, manual-audit sample size, deterministic random seed, and validation rules.

## Commands

```sh
make paper-freeze
make paper-stats
make paper-figures
make paper-audit-sample
make paper-check
```

Recommended broader checks before using numbers in the manuscript:

```sh
make test
make frontend-build
make paper-check
```

## Count Discipline

Do not type corpus counts directly into the manuscript from memory. Regenerate `data/releases/paper_hss_discovery_not_evidence_20260706/paper_stats.json` and cite the matching CSV/Markdown table.

Counts must retain their units:

- live public website display counts;
- local frontend export counts;
- legacy flat-record counts;
- V2 normalized counts;
- strict no-credential record-gate experiment counts;
- lead-mode counts;
- priority lead counts;
- mapped public-record counts;
- source organisation and source type counts;
- blocker counts.

If a count family is not available in current local data, report it as `not available in current local data` rather than substituting a nearby count.

## Double-Anonymous Mode

For journal review, use generated manifests and neutral repository paths. Avoid author-identifying acknowledgements, private notes, machine-local credentials, or personal process details in manuscript files.
