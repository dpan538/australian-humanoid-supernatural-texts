# About Page Redesign Plan — 2026-09-01

Status: planning only. No implementation has started. This document records decisions reached in conversation before any code, copy, or config change is made.

## Purpose

The stated goal of this redesign is promotion/growth, not cosmetic polish. The site currently has poor real-world performance and has not achieved distribution. About is the first page in this pass; its outcome sets direction for the rest of the terminal-style visual system.

Consequence for scope: mobile experience and page-load performance are primary concerns, not secondary ones. Google has used mobile-first indexing for effectively all sites since the 2023-2024 rollout completed — Googlebot crawls and scores Core Web Vitals primarily from the mobile rendering, not desktop. Whatever ships on mobile is what gets indexed and ranked.

**Policy conflict to resolve:** `docs/release/PERFORMANCE_BUDGET.md:3` states "It is not a low-bandwidth mobile-first product." That statement was true for the first release's design intent and is now in tension with the growth/mobile-first goal above. This document does not resolve that conflict; it flags it for an explicit decision before or alongside implementation. Known related fact: `public/data/frontend-data.json` is ~20.7MB in the recorded baseline (`PERFORMANCE_BUDGET.md:16`); the file the About page actually reads, `public/data/frontend-interactive.json`, is ~10MB. Neither is evaluated here — a dedicated performance audit is out of scope for this document and has not been requested yet.

## Scope of this redesign pass

In scope:
- Desktop About page (`app/about/page.tsx`)
- Mobile About view (`components/mobile-archive.tsx:1683` `MobileAboutView`)
- Map page corner readout (`components/archive-terminal.tsx:1774-1780`, `.map-source-block`)
- Global boot/loading overlay copy (`components/archive-terminal.tsx`, `LOADING_TITLE` / `LOADING_INTRO` / `LOADING_BOOT_LINES`, shared across all views)
- `README.md` — four specific additions only (see below)
- Color token values for `--green` / `--blue` and a restrained self-glow treatment

Out of scope this pass (explicitly deferred):
- Light mode redesign — separate task, whole-site CSS effort, not bundled with About
- Any change to `ontology_counts` / record-typology data source (see Finding 2 below) — flagged for a future decision, not resolved here
- Dedicated performance audit (JSON payload size, Core Web Vitals, bundle size)
- Repo slug rename (user will do this manually)

## Confirmed content decisions

### 1. Methodology — single canonical source, four steps

Desktop and mobile currently use independently hand-written wording for the same four-step method (source: `app/about/page.tsx:18-47` vs `components/mobile-archive.tsx:1780-1783`), and the boot overlay uses a third, unrelated three-line version. This has been the single biggest identified consistency failure.

Approved direction: one canonical copy, stored once in code, with mobile deriving from it (e.g. title + first clause) rather than being independently rewritten. Draft (approved by user):

```
01 DISCOVERY / Find a public trace
   Search public archives, libraries, newspapers, digitised books,
   institutional repositories, and community-controlled public sources.
   Tourism pages and unsourced aggregators may point toward a source,
   but are never treated as primary evidence on their own.

02 ADMISSION / Preserve provenance
   A record is admitted only when a public source or public metadata
   entry can be cited. Its source organisation, publication context,
   date, record type, and public-accessibility status stay visible so
   the record can be checked or revised later.

03 CLASSIFICATION / Keep research layers separate
   The label used in the original source, the analytical narrative
   type, the source family, the time period, and the location's role
   in the narrative (event site, apparition site, source institution,
   or cultural region) are coded independently. A shared category
   never implies that culturally distinct beings, traditions, or
   claims are equivalent.

04 LOCATION REVIEW / Map only reviewed evidence
   A record receives a display flag only when it has verifiable
   location evidence. Narrative geography, alleged event geography,
   source location, and broad regional association are tracked
   separately and are never shown as a habitat or as proof.
```

Mobile short form (title + first clause only, not independently rewritten):
`Discovery — Find a public trace.` / `Admission — Preserve provenance.` / `Classification — Keep research layers separate.` / `Location review — Map only reviewed evidence.`

Open decision, still needs a call at implementation time: whether the boot overlay's three-line copy should also be replaced with content drawn from this canonical method, or redone independently as system-check style copy (see Boot Animation section below — user has approved rework but wants content checked in before implementation).

### 2. Data model section — grounded in the real V2 schema

Source: `src/aus_humanoid/v2_schema.py`. Real structure, not to be described loosely:

```
entity_concepts        analytical class, not a species. Schema enforces
                        this at the column level: entity_concepts.not_species_note
                        defaults to "Analytical organization concept only;
                        not a biological species."
      ^
entity_labels           literal label as printed in one source
                        (label_text / normalized_text / label_type),
                        optionally linked to a concept
      ^
source_items  <-- narrative_source_links (18 relationship_type values,
      |            e.g. first_known_attestation, syndicated_reprint,
      |            later_retelling, tourism_retelling) --> narrative_units
      |                                                          |
      |                                                   encounter_events
      |                                                   (optional 1:1 subtype)
      v
narrative_locations (location_role: alleged_event_location,
apparition_location, source_collection_location, publication_location,
cultural_association_region, ...) --> locations
```

**Framing to use (approved for README, see below):** the entity model is object-oriented by design, not taxonomic. `entity_concepts` are classes; `entity_labels` are the literal per-source value; `narrative_units` reference a concept the way an instance references a class. This is a deliberate modelling choice, not an incidental one, and is worth stating plainly.

### 3. Map & display-location policy — split across two surfaces

- **About page (boundary declaration section):** general framing of the rule — a map flag is a reviewed display location, not proof, habitat, or population evidence. Grounded in `narrative_locations.location_role`'s split between narrative-internal locations (`alleged_event_location`, `apparition_location`) and non-eligible location roles (`source_collection_location`, `publication_location`, `cultural_association_region`).
- **Map page corner readout** (`.map-source-block`, currently 2 lines): technical/rendering-specific detail stays here, not About. Verified via live screenshot: the block sits in empty canvas space (near Cape York / Gulf of Carpentaria, top-right), `position: absolute; max-width: min(560px, 42vw)`, no fixed height ceiling, `pointer-events: none`. **A third line is confirmed safe** — no overlap with map shapes, flags, or the adjacent `.map-readout` panel, on desktop or the `≤720px` static-layout mobile variant.
  - Currently missing and worth surfacing here: the source comment in `lib/au-map-data.ts:1-5` carries a disclaimer never shown to users — "Converted to fixed SVG paths for local frontend display; not used as a research source record." This belongs in the corner block, not About.
  - Proposed shape (wording to be finalized at implementation):
    ```
    BOUNDARY: Highcharts Maps Australia subdivisions GeoJSON — display only, not a research source
    TERRAIN: 31 LANDFORM CUES / STATE-CLIPPED
    FLAG RULE: reviewed display location, not proof or habitat
    ```

### 4. Source tiers & evidence standard — approved

Grounded in `config/source_tiers.yml` (A–E) and `docs/release/SOURCE_POLICY.md` (four-layer admission ladder: accepted primary/strong → secondary/context → discovery-only → excluded/restricted). To be presented as a real table, not paraphrased categories. Full detail already captured in conversation; not repeated here in full — pull from those two source files directly at implementation time.

### 5. Ethics & cultural sensitivity — rewrite required, high care

Grounded in `config/ethics_rules.yml` (four principles, four `display_mode` definitions: `full` / `summary_only` / `metadata_only` / `suppressed`) and the migration script's explicit `CONTROL_TERMS` / `TRADITIONAL_TERMS` / `EXCLUSION_TERMS` distinction (`scripts/migrate_legacy_records_v2.py:54-85`) — the project actively excludes specific sacred/creation concepts rather than merely flagging them as sensitive.

**Process requirement, not optional:** exact wording — especially any decision to name specific concepts or communities on the public page — will be drafted and brought back for explicit sign-off before implementation. This document does not pre-approve specific phrasing.

### 6. Project characteristics & contribution

Five-point list approved. Split confirmed:

**Goes in README** (portfolio/technical-contribution framing):
1. `entity_concept` object-oriented framing + `not_species_note` (see §2)
2. The V2 normalized schema itself, already implemented (13 tables, `src/aus_humanoid/v2_schema.py`)
3. Source-chain modelling (`narrative_source_links`, 18 `relationship_type` values)
4. Lead / accepted-record separation (`leads` table, `analysis_status` states including `lead_only`, `excluded`)

**Stays About-only:**
5. Narrative-first (not event-first) modelling — `encounter_events` as an optional 1:1 subtype of `narrative_units`
6. Active cultural-exclusion list (see §5)
7. Auditability claim (contingent on fixing the hardcoded-8 bug and the `ontology_counts` legacy-field issue — see Findings below; the claim should not ship until it is actually true)

### 7. Glossary + data version — paired small module

Terms to define (all real schema/config fields, not invented): `narrative_unit`, `source_item`, `source_tier`, `display_mode` (four real states), `location_role`, `lead`, `publicness_status`. Paired alongside a small revision/version panel: `schema_version` (2.0.0), frontend export `generated_at`, link to release notes.

### 8. Hero

Two non-exclusive options recorded, final call at implementation:
- Trim hero copy (move the record-type enumeration out to the Scope/typology section)
- Reduce the H1 title's font size ~10%, keep copy as-is

## Known bugs / inconsistencies to fix alongside this redesign

1. **Grammar:** `components/mobile-archive.tsx:1792` — "Public source exists does not mean a supernatural claim is verified" reads as a broken sentence when presented as prose (acceptable only as the all-caps telegraphic command-strip banner). Also appears in the shared boot overlay disclaimer line — same fix applies wherever it appears as full-sentence prose.
2. **Hardcoded stat violates the project's own stated principle:** `components/mobile-archive.tsx:1763` — the "REGIONS" count is a literal `<b>8</b>`, not derived from `data`, while the adjacent FIGURES/PERIODS stats in the same card are. README states frontend numbers must derive from the data export, not be hardcoded. Must be fixed before the "auditable" claim (§6, item 7) is used in copy.
3. **Record-typology data source (`ontology_counts`) is a legacy field, not V2 `narrative_type`:** Root cause confirmed by inspecting the live `public/data/frontend-interactive.json` — `ontology_counts` is computed in `scripts/export_frontend_json.py:353` directly from the legacy flat `records.ontology_code` field. It is not simply stale code: the V2 migration itself is incomplete for the largest record category. The live data shows `cryptid_style_apeman` (legacy code) at 1045 records — the single largest bucket in the corpus — while the corresponding V2 `narrative_type` value `encounter_account` shows only 3 records, because most legacy encounter-style records have not yet been promoted into `narrative_units` (migration script explicitly never auto-assigns `analysis_ready`). **Decision needed, not resolved here:** whether the About/Dashboard record-typology panel keeps reading the legacy field (and says so honestly) or waits for fuller V2 promotion. Recommend checking `data/processed/v2/migration_report.md` for actual promotion coverage before deciding — not done in this pass.
4. **Title word-order inconsistency:** README/repo title vs. desktop About H1 (`app/about/page.tsx:94`) use different word orders ("Supernatural Humanoid" vs. "Humanoid Supernatural"). To be unified (repo slug excluded — user handles that manually).
5. **Record-type enumeration inconsistency:** desktop hero prose (`app/about/page.tsx:100`) and mobile hero prose (`components/mobile-archive.tsx:1773-1775`) list different sets of record types; desktop drops "ghost legends" entirely. Resolution: both should draw from the same 7-label set already used in `buildRecordTypeRows` (`app/about/page.tsx:284-303`) rather than being freehand prose — pending the decision in item 3 above about whether that label set itself needs to change.
6. **Imprecise wording, to fix in the copy pass:** "not admitted as primary support" → "never treated as primary evidence"; "Code the printed figure or descriptive label" → resolved by the canonical methodology wording in §1 ("the label used in the original source"); "No DOI is asserted for this live export" → "No DOI is assigned..."; "are not interchangeable counts" → reword for clarity.
7. **Mobile badge grammar mismatch:** `components/mobile-archive.tsx:1695-1697` — "public text" / "auditable" (adjectival) vs. "Australia" (bare noun, not parallel). Needs a consistent grammatical form or a rethink of what the three badges each communicate.
8. **Missing citation content on mobile:** desktop About has a full citation panel; mobile About currently has none. Confirmed gap, to be added (see mobile plan below).

## README additions (approved, four items only)

1. Object-oriented entity model framing (§2 draft paragraph)
2. The implemented V2 normalized schema as a concrete technical accomplishment
3. Source-chain modelling (`narrative_source_links` relationship types)
4. Lead / accepted-record separation

Nothing else moves into README this pass. Map/display-location policy explicitly stays About-only.

## Boot animation (global loading overlay)

Confirmed shared across all views (`components/archive-terminal.tsx`, not dashboard-specific): `LOADING_TITLE`, `LOADING_INTRO`, `LOADING_BOOT_LINES` (lines ~45-50), rendered during the "view initializing" state for map/density/dashboard alike. User has approved a rework (current copy is an early experimental draft) but **requires content to be checked in with them before implementation** — this document does not contain final boot copy.

## Visual system

### Color tokens

Corrected understanding: both `--green` (`#a8ff6a` dark mode) and `--blue` (`#7cc3ff` dark mode, `app/globals.css:91-92`) currently read as not-quite-terminal. Direction: adjust the actual hue/value of both tokens, not their relative usage frequency. Add a restrained self-glow/self-illumination effect — explicitly a supporting accent, not the dominant visual treatment. CRT-phosphor-style `text-shadow`/blur techniques are the likely mechanism but must be used sparingly.

This is a shared design-token change (affects every page, not just About) and should be sequenced deliberately alongside the About content work, not silently folded into a single CSS pass without visibility.

### Light mode — deferred, separate task

Not in scope this pass. Root-cause finding for later reference: `:root[data-theme="light"]` sets `--terminal-scanline` and `--terminal-grid-line` to `rgba(0,0,0,0)` (`app/globals.css:196-197`) — fully transparent. Light mode does not have its own version of the terminal texture; it disables the texture system outright. Only one shadow/glow rule in the entire stylesheet has a light-mode-specific value. This confirms the "done in a rush" assessment and should inform the eventual light-mode redesign, but is out of scope here.

## Mobile About restructure (approved)

Current state: four accordion cards (`Scope` / `Method And Rigour` / `Limits And Ethics` / `Open Project`, `components/mobile-archive.tsx:1683-1818`), no citation content at all.

Proposed card set (accordion pattern retained, grouped to avoid excessive card count):

1. Hero (shortened, matches desktop)
2. Boundary declaration (new — "what this is / is not," folds in general map-policy framing)
3. Scope (existing, keep)
4. Approach (existing Method card, canonical wording from §1)
5. How the archive is structured (new, combined card: data model summary + source-tier A–E table as two sub-sections in one card, not two separate top-level cards)
6. Ethics & Cultural Sensitivity (split out from the current "Limits" card into its own entry, given the weight this content now carries — should not be buried under a generic "Limits" heading)
7. What this contributes (new — characteristics + the three About-only contribution points from §6)
8. Citation (new — currently a real gap, not present on mobile at all)
9. Glossary & Data Version (new, paired sub-sections in one card, mirrors the desktop pairing)
10. Open Project (existing repository card, keep)

## Process notes / sign-off still required before any implementation

- Ethics section exact wording (§5) — explicit sign-off required, not a default-approve item
- Boot animation final copy — check in before implementation
- Record-typology / `ontology_counts` data-source decision (Finding 3) — needs a decision, not resolved here
- Hero: trim vs. font-size reduction — pick one (or both) at implementation time
- Color token exact values and glow implementation — sequencing relative to About content work to be confirmed

## Addendum 2026-09-11 — terminal pass round 2 (implemented, desktop dark only)

Every rule below is scoped to `:root:not([data-theme="light"])`; light mode was not restyled (it only inherits the two structural changes marked *both themes*).

**Display face.** Silkscreen tried and rejected (ugly, readability first). VT323 (`--font-terminal-display`, `app/layout.tsx`) is used only at page-title size: the About hero `h1`, the Source `h2`, and the archive-index `h1`. Numerals, index digits and every reading element stay in the typewriter mono; the About status readouts are bold and ~1.2× larger.

**Cursor-lit text.** Rejected first version was a halo around the pointer. Now: `TerminalCursorGlow` publishes `--cursor-x/--cursor-y` on `<html>` from one passive, rAF-coalesced `pointermove`; chrome text paints a viewport-fixed radial gradient into its glyphs (`background-clip: text`, 180px radius). Per accessibility feedback, reading text (section `h2/h3`, list terms, index digits, prose) is excluded; only page titles, prompt labels, command strip and readouts take the sheen, and the lit colour stays in the element's own hue (blue → lighter blue, ink → white), so contrast only rises. Off under reduced motion / coarse pointers; light mode never consumes the variables.

**CLI grammar (no sci-fi ornament).** `> ` prompts on `.tiny-label`, kickers and panel headers; `[ ]` around rigour-panel counters and index-page section titles; `// ` on typology subtitles; blinking `█` caret on the About command strip and the Source FILTER line while empty; Record Typology rows carry a dotted leader plus a block bar on a dim track (`.about-typology-bar`, `--share` computed server-side). The earlier circuit-line ornament, `.view-area` shadow, scanline opacity bump and prompt/bar opacity tweaks were all removed ("不要乱用 drop shadow 或者改变 opacity"). LED breathing is a scale-only transform on a static `::after` halo; the Source header LED now shares it.

**Desk vs. canvas.** `body`/`.terminal-shell` desk is `#0a0b0a`; every canvas is `var(--panel)` inside a 1px border. Figures had its green panel tokens swapped for the ink/blue register (green survives as LED/accent only).

**Source page.** Canvas restored to the same bordered proportions as other views; register fills it — the base row template (`auto auto 1fr auto`) assumed the mobile tab strip and dropped the split pane into an `auto` row above 720px, fixed with `auto minmax(0,1fr)`. Flat canvas (no inner frame overlay), uniform dividers, blue selected row with green bracket, `:focus-visible` outline. Rollup rows: 11px vertical padding, labels clamped to two lines, numeric columns tightened, a legend footer (`.source-pane-footer`, *both themes*) naming marker / dot-train / ORGS; the type rows lost their dot trains because most display types hold 1–5 records against a 1,600-record family peak (blind viz). Inspector: kicker above a real heading, three columns sized to their content (`1.15fr / 1.5fr / 0.72fr`) with a 13ch label column and wrapping values. The dock-clearance end space (`--archive-scroll-end-space`) is removed from both Source lists — it was the void under their last rows. The ethics note is one formal `> NOTICE` line (0.92rem, nowrap) below the canvas fold; `.source-view` scrolls (scrollbar hidden) to reveal it with 44/36px of room.

**Figures.** The top `MAP / DENSITY / DASHBOARD` strip was removed (*both themes*); all navigation goes through the bottom dock.

**Archive index pages** (`components/archive-publication.tsx`: `/records`, `/data`, `/cite`, `/sources`, `/places`, `/periods`, `/narrative-types`, every `/records/[slug]`). Structural (*both themes*): the top console nav (`ARCHIVE INDEX MODE` + five links) is gone, replaced by a brand line; the index family's links live on one `> INDEX` line in the footer (`Records / Types / Sources / Places / Periods / Data / Cite`); the shared bottom dock (theme control, About / Source / Index→Map) is added; footer grammar fixed. Dark restyle: one bordered canvas (`.publication-canvas`) on the desk, flat sections separated by rules, VT323 `h1`, `> ` prompts on eyebrow/breadcrumb/stat labels, dotted separators in definition lists, sticky dock carrying the desk colour.

**Still open from this round:** visual sign-off on VT323 title sizes and the 180px glow radius; light-mode pass (deferred); `MobileThemeControl` icon FOUC; README additions; map-corner policy text; boot overlay rewrite (content check-in first); `ontology_counts` data-source decision.
