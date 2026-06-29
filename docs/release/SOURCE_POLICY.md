# Public Source Policy

This project documents public source records. It does not verify supernatural claims, cultural authority, or real-world occurrence.

Public availability is a necessary condition for release display, but it is not sufficient by itself. Public metadata is not permission to reproduce or reclassify culturally sensitive material.

## Accepted Primary Or Strong Sources

Accepted primary or strong sources include:

- public archives;
- state libraries;
- municipal local-studies collections;
- public-domain books;
- institutional repositories;
- public newspapers and stable media articles;
- museums and heritage organisations;
- community-controlled public sources where publicness is clear.

These sources can support public records when the source item has a stable citation, public access status, source name or organisation, and substantive narrative or catalogue evidence.

## Secondary And Context Sources

Secondary/context sources include:

- scholarly commentary;
- media commentary;
- public catalogue metadata with substantive description;
- later retellings;
- public heritage discourse.

Secondary/context sources may support public display when they are clearly labelled and not presented as first-hand proof. Catalogue metadata with only a pointer or title should be treated as review material unless it contains enough substantive public description to support a public record.

## Discovery-Only Sources

Discovery-only sources include:

- tourism pages;
- haunted-tour pages;
- Wikipedia;
- paranormal aggregators;
- unsourced listicles;
- search result pages;
- metadata-only pointers;
- unresolved leads.

Tourism pages can identify leads or later public retellings, but they are not primary evidence unless backed by a stronger source.

Discovery-only sources may remain in review queues, route logs, or source audits. They should not be treated as strong public evidence without an accepted source chain.

## Excluded Or Restricted Sources

Excluded or restricted sources include:

- secret/sacred material;
- non-public material;
- restricted community-controlled content;
- anonymous unsupported claims;
- AI-generated pages;
- non-Australian narratives incorrectly imported;
- non-humanoid phenomena unless clearly labelled as control/context.

Collectors and release scripts must not bypass paywalls, login walls, access restrictions, cultural restrictions, robots expectations, or takedown requirements.

## Release Audit Expectations

Before release, run:

```sh
python3 scripts/check_vercel_release.py
make validate-v2
make audit-v2
```

Run V2 make targets with a timeout when the local Python/data environment is ready.

Review:

- tourism-only accepted rows;
- Wikipedia accepted as source rather than pointer;
- raw metadata counted as a substantive record;
- excessive source concentration;
- duplicate source organisations under slightly different names;
- raw enum labels leaking into the public UI.
