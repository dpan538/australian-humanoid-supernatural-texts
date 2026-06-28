# Mobile And Small-Screen Assessment

The first release is desktop-first and small-screen usable, but it is not a fully dedicated mobile product.

Assessment viewports:

- 390 x 844
- 430 x 932
- 768 x 1024
- 1024 x 768
- 1440 x 900

## Page Assessment

| Page | Classification | Notes |
|---|---|---|
| About | small-screen-usable | Text should remain readable and sections should stack. |
| Map | small-screen-usable | Map can be inspected, but dense marker interaction is better on desktop. No claim of full mobile map ergonomics. |
| Dashboard | small-screen-usable | Panels should remain readable with stacked or scrollable layout. |
| Density | small-screen-usable | Dense labels require spot checks at 390 px and 430 px widths. |
| Source | small-screen-usable | Source tables/registers should remain scrollable; desktop splitter interactions are primary. |

## Checks

For each viewport, manually verify:

- readable text;
- no horizontal overflow;
- navigation usable;
- touch targets acceptable;
- record overlay fits viewport;
- map usable without hover;
- source tables usable;
- dashboard panels usable;
- density labels readable.

## Release Stance

The first public release can launch as desktop-first and small-screen usable. Do not describe it as a dedicated mobile design until mobile-specific interaction design and QA are completed.

