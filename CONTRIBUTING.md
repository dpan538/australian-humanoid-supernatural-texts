# Contributing

Contributions should preserve the project as a source-grounded public-text research archive.

## Ground Rules

- Use stable public sources or public metadata records.
- Do not add unsourced claims or present supernatural claims as verified facts.
- Do not convert traditional, spirit-person, ancestral, or culturally specific records into cryptid species.
- Do not add restricted, secret/sacred, non-public, paywalled, or culturally restricted material.
- Keep tourism pages, paranormal aggregators, and unsourced listicles as leads unless stronger public source support exists.
- Preserve source labels and exact source/community terminology where public and appropriate.
- Keep public map flags limited to verified display locations under the map eligibility policy.
- Preserve the split license model in `LICENSE.md`, `LICENSE-MIT.md`, and `LICENSE-VISUAL.md`.

Before opening a release-oriented change, run:

```sh
npm ci
npm run typecheck
npm run build
```

Run `make test` only when the local Python test environment is installed and ready.
