# Public Map Eligibility

A public map flag is a verified display location for a public record. It is not proof that an event happened.

## Core Rule

One public record can produce zero or one public map flag.

All eligible map flags must satisfy the release invariant:

```text
mapped_record_count == map_points.length == map_flags.length
```

## Required Evidence

A public map flag requires:

- source-stated place evidence;
- coordinate evidence;
- verification status;
- an Australian jurisdiction;
- a public record that is not suppressed, restricted, rejected, or scope-excluded.

Publication locations and institution addresses are not valid event/map points. State-only or broad-region records do not become strict flags.

## Allowed Map Roles

Allowed public map roles are:

- alleged event location;
- apparition location;
- legend-associated place;
- narrative setting;
- rumour circulation place.

The existing frontend exporter also retains closely related review roles such as source-visible place hints, but those remain subject to coordinate and verification checks before public display.

## Disallowed Map Roles

Disallowed public map roles are:

- publication location;
- archive custody location;
- source institution address;
- author residence;
- inferred state-only location;
- broad cultural region without display clearance.

## Sensitive Or Broad Records

Culturally sensitive, broad-region, or ambiguous records may be public as summary-only records while remaining unmapped. A missing map flag does not imply that a record is less important; it only means that the release map cannot display a verified point under the public map policy.

