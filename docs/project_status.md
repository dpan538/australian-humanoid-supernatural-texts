# Project Status

Last updated: 2026-06-19

## Current Repository State

The project currently contains a reproducible SQLite-backed research-data and
frontend-display foundation for public Australian textual records about
humanoid or humanoid-adjacent supernatural beings.

The frontend is an archive-terminal interface with four routable pages:

- `/map`
- `/dashboard`
- `/density`
- `/source`

The map/dashboard/density views read exported display data from
`public/data/frontend-data.json`. Record overlays are generated only from rows
that pass the card-readiness gate.

## Data State

The current SQLite database contains 985 display records.

All 985 records are card-ready. In this project, card-ready means that a record
has:

- year
- title or figure/event name
- public source URL
- source/publicness metadata
- snippet or objective display description
- coding row
- at least one location link

Search leads, empty source hits, and pages without enough fields for a record
card are not counted as records.

## Latest Collection Round

The latest completed collection round increased the database from 707 to 985
records, for a net gain of 278 verified card-ready records.

The user-requested target for the broader follow-up round was +500 records. The
collector was stopped at the nearest clean checkpoint before reaching that
number because available public sources did not yield enough additional
card-ready rows without lowering the record standard.

No synthetic smoothing was applied to regional coverage. If a state or territory
is underrepresented, that is preserved as source evidence rather than corrected
by artificial balancing.

## Current Coverage Summary

Date coverage:

- 1803-1841 backsearch: 3 records
- 1842-1875 anchor: 27 records
- 1876-1969 expansion: 117 records
- 1970-present modern: 838 records

Region coverage:

- ACT: 17
- AU_UNSPECIFIED: 24
- NSW: 453
- NT: 25
- QLD: 318
- SA: 11
- TAS: 6
- UNKNOWN: 2
- VIC: 87
- WA: 46

Location confidence:

- high: 632
- medium: 335
- low: 18
- unknown: 0

Source coverage:

- Australian Yowie Research: 898
- OpenAlex: 56
- Internet Archive: 13
- Crossref: 11
- English Wikipedia: 6
- ABC News: 1

## Guardrails

The collection scripts preserve the project ethics boundary:

- only public, published, openly discoverable sources are used;
- restricted, secret/sacred, unpublished, or non-public materials are not
  collected;
- public metadata is treated as a display/review signal, not permission to
  extract restricted cultural knowledge;
- Indigenous cultural material is coded with source voice, publicness, and
  mediation rather than flattened into a generic monster category.

## Known Limits

The corpus is modern-heavy and strongly weighted toward NSW and QLD because the
largest currently accessible public source, Australian Yowie Research, is
weighted that way.

Trove would be the best next source for earlier and more regionally balanced
public newspaper coverage, but the official API requires a valid Trove API key.
The current repo does not include credential-dependent scraping or protected
endpoint bypass logic.

The latest AYR location-hint dry run found no additional insertable records
after existing duplicates and card-readiness checks. Remaining AYR section/media
items are retained as candidate evidence only when their location cannot be
verified well enough for a record card.
