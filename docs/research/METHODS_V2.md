# Methods V2

V2 is a typed, provenance-aware migration of the legacy flat-record corpus.

Method sequence:

1. Freeze the legacy corpus and checksums.
2. Add normalized source, narrative, label, location-role, review, lead, and exclusion tables.
3. Map every legacy record to a source item.
4. Promote only sufficiently described legacy rows to narrative units.
5. Preserve exact source labels separately from analytical entity concepts.
6. Separate event, apparition, legend, cultural association, publication, and uncertain locations.
7. Export review CSVs and frontend-data/v2.
8. Stage new collection candidates before acceptance.

The migration is a first-pass deterministic classification. It supports review; it is not a substitute for human scholarly coding.

