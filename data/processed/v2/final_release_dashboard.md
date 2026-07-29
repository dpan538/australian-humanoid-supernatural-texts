# Final Release Dashboard

## 1. Release Status
- Status: `ready`

## 2. 1926-2011 Coverage
- Accepted records, metadata-only items, and leads are reported as separate layers.
- Remaining caveats are in `final_release_known_limitations.md`.

## 3. Map
- Accepted public map count: `1593`
- Metadata overlay count: `1552`
- Lead overlay count: `1448`
- Unmapped gap items: `0`

## 4. Redirects
- Redirect validation: `PASS`

## 5. Source Concentration
- Source-chain caveats remain labelled; discovery/access layers are not accepted evidence.

## 6. What Changed
- Release layers added.
- Public records unchanged.
- Map flags unchanged.

## 7. Next Command
- `python3 scripts/apply_final_release_package.py --package-dir data/processed/v2/final_release_package --execute`
