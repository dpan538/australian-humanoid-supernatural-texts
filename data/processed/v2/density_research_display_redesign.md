# Density Research Display Redesign

## Scope

This change updates the Density view only. It does not modify canonical data, SQLite, frontend export semantics, record years, map eligibility, public counts, or route structure.

## Methodological Defect

The previous main period display allowed `1876-1969` to dominate the public density row. That band is too broad for a release-facing temporal display and can imply a forced prior. This is treated as a time-binning methodological display bug.

## Why Equal Duration Is Not The Only Method

Pure equal-duration bins are useful as a test, but they are not the default public reading lens for this archive. The project studies Australian public texts and source environments, not natural event frequency. A default display needs readable public-text context bands, while the comparator shows how different periodisation choices affect the visual result.

## Historical-Context Period Definitions

The default Density overview uses six historical/public-text context bands:

| Period | Context label |
| --- | --- |
| 1825-1850 | Early colonial public records |
| 1851-1900 | Late colonial press / Federation lead-up |
| 1901-1918 | Federation and First World War |
| 1919-1945 | Interwar and Second World War |
| 1946-1990 | Postwar / broadcast / local-history accumulation |
| 1991-latest data year | Web / digitisation / repository era |

The first and last boundaries are clamped to the actual dated public-record span. If future data extends beyond the current latest year, the final band extends automatically.

These are context anchors for publication and public-text environments. They do not claim that Federation, wars, migration, digitisation, or web repositories caused supernatural record counts.

## Equal-Duration Method

The equal-duration lens divides the actual dated public-record span into six mechanical bins:

```text
binWidth = ceil((maxYear - minYear + 1) / 6)
```

This comparison tests whether the visual pattern is partly caused by uneven period widths.

## Equal-Record Method

The equal-record-count lens uses dated public records only, sorts by year, and splits the records into six near-equal groups while keeping same-year records together where possible. This is a comparison tool: it makes periods visually balanced but can hide real temporal concentration.

Undated records are shown as a compact note and are not forced into a false period.

## Page Structure

Field 01, Density Overview, now uses the historical-context scheme by default. It shows six period cards, a methodological note, figure/narrative cards, and a selected-period summary. The prior Source Field panel is not present on Field 01.

Field 02, Period Method Comparator, compares Historical Context, Equal Duration, and Equal Record Count using the same six-block visual grammar.

Field 03, Analytical Field, provides one period lens selector and four analysis tabs:

- Temporal × Narrative
- Source Bias
- Map Coverage
- Regional Profile

All chart language is framed as archive record density, source coverage, or map eligibility. No chart claims real-world event frequency or causation.

## QA Screenshots

Screenshots are stored in:

```text
data/processed/v2/density_period_method_screenshots/
```

Required captures:

- `field_01_desktop_overview.png`
- `field_01_figure_card_inspector.png`
- `field_02_period_comparator.png`
- `field_03_temporal_narrative.png`
- `field_03_source_bias.png`
- `field_03_map_coverage.png`
- `field_03_regional_profile.png`
- `mobile_field_01.png`
- `mobile_field_02.png`
- `mobile_field_03.png`

## Verification Notes

- `1876-1969` no longer appears as the dominant main Density period.
- Field 01 uses historical-context periods.
- Field 02 exposes equal-duration and equal-record methods as comparisons.
- Field 03 charts update from the period lens selector.
- Figure/narrative cards remain prominent on Field 01.
- Source Field is not shown on Field 01.
- Methodological disclaimer states that period lenses organise public records and do not establish real-world frequency or causation.
- New CSS includes mobile-specific layout rules for the three-field structure.
- `npm run build` passed after the redesign.
- Localhost route checks passed for `/about`, `/map`, `/dashboard`, `/density`, and `/source`.
- Chrome DevTools QA found no serious console events during Density navigation and tab switching.

## Remaining Limitations

The Density view remains a research display rather than a full analytics product. It intentionally limits the method set to three period schemes and four analysis tabs. Equal-record bins preserve same-year groups where possible, so record counts may not be perfectly equal.
