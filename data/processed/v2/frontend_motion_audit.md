# Frontend Motion Audit

Generated: `2026-06-28`

Motion policy: data-heavy views use bounded reveal animation; interaction
motion stays short; ambient terminal breathing is limited to a few non-text
status elements.

## Inventory

| Page | Component | Tier | Trigger | Targets | Properties | Loop | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Map | `useMapFlagGrowth` | A | map data load | `.record-flag-dot` | opacity, instant by chunk | no | keep |
| Map | `useMapAmbientMotion` | C | map mount | readout LED, source legend glyphs | opacity, scale | yes | keep |
| Dashboard | `useDashboardLayoutMotion` | A | dashboard mount/layout | draw paths, visible nodes, metric rows | opacity, transform, stroke-dashoffset | no | keep |
| Dashboard | `useDashboardFieldMotion` | B | field switch | current field panel elements | opacity, transform, stroke-dashoffset | no | keep |
| Source | `useSourceTerminalMotion` ambient | C | source mount | small LEDs, divider ticks, active source marker | opacity, scale | yes | keep |
| Source | `useSourceTerminalMotion` selection/filter | B | selection/filter change | selected bracket, inspector line, result marker | opacity, scale | no | keep |
| About | `AboutAmbientMotion` | A/C | about mount | flow lines, status LED, live raster cells | opacity, scale, stroke-dashoffset | yes | keep |

## Release Notes

- Map reveal is chronological accumulation of record quantity, not individual dot growth.
- Map markers settle as static pure color dots.
- No continuous animation runs on all map markers.
- Source and About keep subtle ambient motion only on small non-text indicators.
- Dashboard animations are finite and interaction-scoped.
- Reduced motion disables reveal and ambient loops while keeping content visible.
- Visibility-aware ambient loops stop when the tab is hidden.
