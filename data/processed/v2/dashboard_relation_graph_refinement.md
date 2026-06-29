# Dashboard Relation Graph Refinement

## What was wrong

The previous dashboard state kept the right broad structure, but the left relation graph was too opaque and the track list collided with the graph. In expanded mode, the inspector sat on top of graph nodes and edges. On narrow screens, the left panel was effectively a scaled desktop graph, which made labels unreadable and caused white track notes to block the relationship field.

## Track column movement

The expanded left panel now uses vertical flow inside the existing terminal frame. The relation graph is rendered first as its own scrollable section, and the track inspector appears below it instead of occupying a narrow side column. The inspector has its own bounded row scroll, so graph content and track rows no longer compete for the same space.

## Graph lane structure

The graph is organized into four persistent lanes:

- SOURCE
- PERIOD
- NARRATIVE
- PLACE

Major nodes show persistent labels and aggregate counts. Edges connect actual public-record aggregates between adjacent lanes. The balanced desktop view reserves a compact graph zone and a separate track-preview zone. The mobile balanced view uses a dedicated compact track snapshot rather than scaling the full lane graph down.

## Colour semantics

- cyan: repository, public-domain, and mapped/place relationships
- amber: period and historical ordering
- violet: narrative categories and academic/source-style links
- green: active selected relationship
- ivory/muted: neutral structure and inactive data

Source styles are explained in a visible legend. Edge hierarchy uses opacity and width so inactive relationships remain present while the active relationship is readable.

## Track ordering logic

Tracks are selected from the active relation and ordered by year, source, and title. If no relation is locked, the strongest relation group is used. Rows include title and public metadata in expanded mode. Hover/focus highlights the corresponding graph relation; click locks the relation and opens the existing record overlay.

## Chart typography changes

Dashboard-specific readable font variables were added. Chart labels, legends, source names, state labels, and track text were enlarged where they were too small. Secondary selected-period strips were reduced in visual dominance.

## Timeline changes

The console timeline now uses thinner strokes and layered public aggregates: total records, mapped-record subset, and a compact diversity signal. Peak and selected points settle into a static readable state after Anime.js entry motion.

## Source donut changes

The source composition section is larger in the expanded right panel. The donut uses a readable diameter with a full legend showing source-family label, count, and percentage. Truncated source labels were removed from the main legend where space allows.

## Scroll behavior

Left-expanded mode scrolls vertically within the left panel: graph first, track inspector below. Right-expanded mode scrolls vertically for larger timeline, matrix, source, and jurisdiction modules. Mobile balanced left mode now shows a compact responsive snapshot with white notes and small track lines, avoiding the direct-scaled graph.

## Screenshots captured

- Balanced desktop: `/private/tmp/dashboard_balanced_refined_fixed.png`
- Left-expanded graph: `/private/tmp/dashboard_left_expanded_top_refined.png`
- Left-expanded track inspector after scroll: `/private/tmp/dashboard_left_expanded_tracks_refined.png`
- Right-expanded top: `/private/tmp/dashboard_right_expanded_top_refined.png`
- Right-expanded source section: `/private/tmp/dashboard_right_expanded_source_refined.png`
- Mobile balanced left snapshot: `/private/tmp/dashboard_mobile_left_snapshot_fixed.png`

## Mobile result

At 390 x 844, the left panel no longer scales the full relation graph into a tiny unreadable diagram. It shows a compact track snapshot with a relation heading, six readable white notes, and small source-coloured connector lines. The full graph remains available in larger/expanded layouts.

## Build result

`npm run build` passed with Next.js static generation for `/dashboard`, `/map`, `/density`, `/source`, and `/about`.

## Remaining limitations

The balanced desktop graph is intentionally compact to preserve the original information density and right-side console. The mobile snapshot shows the top six relation tracks rather than the full lane graph, so deep relationship exploration is still best in expanded mode.

## Files changed

- `components/archive-terminal.tsx`
- `app/globals.css`
- `package.json`
- `package-lock.json`
- `data/processed/v2/dashboard_relation_graph_refinement.md`
