import { readFile } from "node:fs/promises";
import path from "node:path";
import type { CSSProperties } from "react";
import Link from "next/link";
import { AboutAmbientMotion } from "@/components/about/about-ambient-motion";
import { TerminalCursorGlow } from "@/components/about/terminal-cursor-glow";
import { CitationSamples } from "@/components/citation-samples";
import { DisplayControls } from "@/components/display-controls";
import { MobileArchiveRoute } from "@/components/mobile-archive";
import { RouteStructuredData } from "@/components/route-structured-data";
import { FRONTEND_DATA_URL } from "@/lib/frontend-data";
import { metadataForRoute, siteConfig } from "@/lib/site";
import { buildProjectCitations } from "@/lib/citations";
import { buildMobileArchiveData } from "@/lib/mobile-archive-data";
import { buildSourceRegistryData } from "@/lib/source-view-data";
import type { FrontendData } from "@/lib/types";

export const metadata = metadataForRoute("/about");

const BOUNDARY_IS = [
  {
    index: "01",
    label: "SCOPE",
    title: "Australia only",
    body:
      "Every record ties to an Australian public source, an Australian public metadata entry, or a narrative documented in a public Australian text.",
  },
  {
    index: "02",
    label: "EVIDENCE BASIS",
    title: "Public records and public metadata",
    body:
      "Inclusion means a public source or public metadata record exists and can be cited, reviewed, or linked — not that the account it describes is true.",
  },
  {
    index: "03",
    label: "TYPED FOR REVIEW",
    title: "Coded on five axes",
    body:
      "Narrative role, source family, publicness, date, and location evidence are tracked separately, so any one record can be checked or revised without touching the others.",
  },
  {
    index: "04",
    label: "MAP RULE",
    title: "At most one flag per record",
    body:
      "A map flag is a reviewed display location for one record. It is never shown as proof of an event, a habitat, or a population.",
  },
] as const;

const BOUNDARY_IS_NOT = [
  "Proof that any supernatural entity exists",
  "A complete census of Australian folklore",
  "A habitat or population map",
  "An authoritative Indigenous knowledge repository",
  "Permission to reproduce restricted cultural material",
  "A tourism or haunted-place directory",
] as const;

const METHOD_STEPS = [
  {
    index: "01",
    label: "DISCOVERY",
    title: "Find a public trace",
    body:
      "Search public archives, libraries, newspapers, digitised books, institutional repositories, and community-controlled public sources. Tourism pages and unsourced aggregators may point toward a source, but are never treated as primary evidence on their own.",
  },
  {
    index: "02",
    label: "ADMISSION",
    title: "Preserve provenance",
    body:
      "A record is admitted only when a public source or public metadata entry can be cited. Its source organisation, publication context, date, record type, and public-accessibility status stay visible so the record can be checked or revised later.",
  },
  {
    index: "03",
    label: "CLASSIFICATION",
    title: "Keep research layers separate",
    body:
      "The label used in the original source, the analytical narrative type, the source family, the time period, and the location's role in the narrative (event site, apparition site, source institution, or cultural region) are coded independently. A shared category never implies that culturally distinct beings, traditions, or claims are equivalent.",
  },
  {
    index: "04",
    label: "LOCATION REVIEW",
    title: "Map only reviewed evidence",
    body:
      "A record receives a display flag only when it has verifiable location evidence. Narrative geography, alleged event geography, source location, and broad regional association are tracked separately and are never shown as a habitat or as proof.",
  },
] as const;

const RIGOUR_CHECKS = [
  {
    label: "PROVENANCE",
    value: "Source, public role, record type, and citation path stay inspectable.",
  },
  {
    label: "LAYER SEPARATION",
    value: "Public records, mapped records, metadata-only items, and research leads are counted separately and never summed as one total.",
  },
  {
    label: "ETHICS",
    value: "Culturally specific and sensitive material can be contextualised, summarised, or suppressed.",
  },
  {
    label: "REVISION",
    value: "The corpus is an auditable research display, not a complete or peer-reviewed authority.",
  },
] as const;

const DATA_MODEL_STEPS = [
  {
    index: "01",
    label: "CONCEPT",
    title: "An analytical class, not a species",
    body:
      "entity_concepts group related figures for analysis. The schema enforces the boundary directly: every concept carries a fixed field reading “Analytical organization concept only; not a biological species.”",
  },
  {
    index: "02",
    label: "LABEL",
    title: "The name as printed",
    body:
      "entity_labels preserve the literal wording a source used. A label does not need to be resolved to a concept before it can be stored.",
  },
  {
    index: "03",
    label: "SOURCE CHAIN",
    title: "How a record reached this page",
    body:
      "narrative_source_links tie a narrative to its sources through one of eighteen tracked relationship types — first attestation, syndicated reprint, later retelling, tourism retelling — so discovery and evidentiary weight stay distinguishable.",
  },
  {
    index: "04",
    label: "LOCATION ROLE",
    title: "Where geography does and doesn't count",
    body:
      "narrative_locations tags each place with a role. Only narrative-internal roles, such as an alleged event or apparition location, are eligible for a map flag; a source's collection address or a broad cultural region is not.",
  },
] as const;

const DATA_MODEL_NOTES = [
  {
    label: "CLASS VS. INSTANCE",
    value: "A concept is a class; a label is the literal value one source used.",
  },
  {
    label: "OPTIONAL SUBTYPE",
    value: "encounter_events exist only where a narrative has a bounded event — most narrative units have none.",
  },
  {
    label: "PARTIAL COVERAGE",
    value: "Not every legacy record has been promoted into this model yet. Record Typology below still reflects the fuller legacy classification where V2 coverage is incomplete.",
  },
] as const;

const SOURCE_TIERS = [
  {
    index: "A",
    label: "TIER A",
    title: "Primary or near-primary public source",
    body:
      "Trove newspapers and magazines, NLA digitised items, original public books, diaries, and memoirs, Internet Archive public-domain texts.",
  },
  {
    index: "B",
    label: "TIER B",
    title: "Public institutional or community-controlled source",
    body:
      "AIATSIS public material, state libraries and archives, public museums and galleries, heritage authorities.",
  },
  {
    index: "C",
    label: "TIER C",
    title: "Public circulation and reputable retelling",
    body: "ABC, SBS, reputable journalism, local-history organisations.",
  },
  {
    index: "D",
    label: "TIER D",
    title: "Scholarly secondary study",
    body:
      "Accepted when accessible content carries substantive relevant material — metadata alone is a pointer, not evidence.",
  },
  {
    index: "E",
    label: "TIER E",
    title: "Discovery-only or specialist aggregator",
    body:
      "Accepted only when a stable page carries substantive narrative and the source's mediation stays visible on the record.",
  },
] as const;

const ADMISSION_LADDER = [
  {
    label: "ACCEPTED",
    value: "Stable citation, public access, and substantive evidence support a public record.",
  },
  {
    label: "SECONDARY / CONTEXT",
    value: "Clearly labelled as commentary or retelling — never presented as first-hand proof.",
  },
  {
    label: "DISCOVERY-ONLY",
    value: "Tourism pages, Wikipedia, and paranormal aggregators can point to a lead. They are not evidence on their own.",
  },
  {
    label: "EXCLUDED",
    value: "Secret/sacred material, non-public content, and unsupported anonymous claims are not collected.",
  },
] as const;

const ETHICS_PARAGRAPHS = [
  "Public discoverability does not by itself authorise reproduction. A public catalogue record is a signal that something exists, not permission to extract restricted cultural knowledge from it. Restricted, secret/sacred, unpublished, or community-controlled material is not collected. Where a source uses its own community's terminology, that terminology and its original context are preserved rather than rewritten.",
  "Every narrative record carries a display state, set at review time: shown in full with a neutral summary and short excerpt; shown as a neutral summary only, with sensitive substance not reproduced; shown as source metadata only, with no narrative content; or withheld entirely from public display. This state is a review decision, not a default — sensitivity is assessed per record, not assumed from a source's origin.",
  "Some concepts are not merely handled with caution — they are excluded from the archive outright. Where a narrative concept functions as sacred or creation knowledge rather than a locally circulating legend, it falls outside this project's scope entirely and is not catalogued, labelled, or cross-referenced here.",
  "A smaller set of traditional narrative concepts carry an elevated sensitivity setting by default, set before any individual record is reviewed. This does not suppress them from the archive, but it raises the bar for what can be shown in full and keeps source-community terminology intact rather than replaced with an analytical label.",
] as const;

const DISPLAY_STATES = [
  { label: "FULL", value: "Neutral summary and short excerpt shown." },
  { label: "SUMMARY ONLY", value: "Neutral summary and metadata shown; sensitive substance is not reproduced." },
  { label: "METADATA ONLY", value: "Source metadata shown; no narrative content." },
  { label: "SUPPRESSED", value: "Withheld entirely from the public export." },
] as const;

const CONTRIBUTION_POINTS = [
  {
    index: "01",
    label: "NARRATIVE-FIRST",
    title: "Built around narratives, not sightings",
    body:
      "The base object is a documented narrative, not a bounded encounter — see Data Model above. Most cryptid-style catalogues default to the opposite, which quietly treats every record as a claimed event.",
  },
  {
    index: "02",
    label: "EXCLUSION AS POLICY",
    title: "Exclusion, not just caution",
    body:
      "This project doesn't only flag sensitive concepts for careful handling — for some, it declines to catalogue them at all. See Ethics & Cultural Sensitivity above.",
  },
  {
    index: "03",
    label: "EXPORT-DERIVED NUMBERS",
    title: "Every count traces to one file",
    body:
      "The figures on this page are read from a generated data export, not maintained by hand — see Glossary & Data Version below.",
  },
] as const;

const RESEARCH_THREAD_NOTE = {
  label: "IN PROGRESS",
  value:
    "These three points are the empirical basis for a methods paper in development, on how archives like this one should separate discovery from evidence.",
};

const GLOSSARY_TERMS = [
  { term: "narrative_unit", body: "The archive's core research object: one documented narrative, legend, or account." },
  { term: "source_item", body: "One cited public source — a newspaper article, book, catalogue entry, or page." },
  { term: "source_tier", body: "A–E grading of how strong a source is as evidence (see Source Standards)." },
  { term: "display_mode", body: "How much of a record is shown publicly: full, summary only, metadata only, or suppressed." },
  { term: "location_role", body: "What a place means to a narrative — an event site, a source's address, and a cultural region are not treated the same." },
  { term: "lead", body: "An unresolved pointer to a possible source, not yet an accepted record." },
  { term: "publicness", body: "Whether a source is publicly accessible and citable, tracked independently of how strong it is as evidence." },
] as const;

export default async function AboutPage() {
  const data = await loadAboutData();
  const mobileData = buildMobileArchiveData(data);
  const statusCells = buildStatusCells(data);
  const recordTypeRows = buildRecordTypeRows(data);
  const exportDate = data.generated_at.slice(0, 10);
  const citationSamples = buildProjectCitations(exportDate);

  return (
    <>
      <MobileArchiveRoute view="about" data={mobileData} />
      <main className="terminal-shell desktop-about-shell">
      <div className="noise-layer" aria-hidden="true" />
      <TerminalCursorGlow />
      <RouteStructuredData path="/about" />
      <div className="terminal-stage">
        <section className="view-area view-area-about" aria-label="About this archive terminal">
          <div className="about-view">
            <AboutAmbientMotion />

            <header className="about-hero">
              <div className="about-hero-copy">
                <span className="tiny-label">ABOUT / PUBLIC DATA TERMINAL</span>
                <div className="mobile-about-heading">
                  <span>ABOUT</span>
                  <h1>AusFigures</h1>
                  <p>Source-grounded public records of Australian supernatural humanoid narratives.</p>
                </div>
                <h1 className="about-desktop-title">AUSTRALIAN SUPERNATURAL HUMANOID TEXTS</h1>
                <p className="about-subtitle">Public-text archive and research display system</p>
                <p>
                  This project traces how humanoid or humanoid-adjacent supernatural figures appear in Australian public texts — encounters, apparitions, legends, and their later retellings. Inclusion means a public source or public metadata record exists; it does not verify the claim that source describes.
                </p>
              </div>

              <aside className="about-status-panel" aria-label="Public corpus status">
                <div className="about-status-head">
                  <i className="about-status-led" aria-hidden="true" />
                  <span>DATA STATUS / PUBLIC CORPUS</span>
                </div>
                <div className="about-status-grid">
                  {statusCells.map((cell) => (
                    <b className="about-status-cell" key={cell.label}>
                      <span>{cell.label}</span>
                      <strong>{cell.value}</strong>
                    </b>
                  ))}
                </div>
              </aside>
            </header>

            <section className="about-command-strip" aria-label="Archive display rule">
              <i aria-hidden="true" />
              <span>SOURCE-GROUNDED PUBLIC-TEXT ARCHIVE</span>
              <b>PUBLIC SOURCE EXISTS != SUPERNATURAL CLAIM VERIFIED</b>
            </section>

            <section className="about-research-board" aria-labelledby="about-boundary-title">
              <header className="about-research-head">
                <div>
                  <span className="tiny-label">SCOPE / BOUNDARY DECLARATION</span>
                  <h2 id="about-boundary-title">A record of public texts, not a verification system.</h2>
                </div>
                <p>
                  This archive studies how supernatural humanoid figures are represented in public Australian sources. It does not test whether any reported figure or event is real.
                </p>
              </header>

              <div className="about-method-layout">
                <ol className="about-method-sequence">
                  {BOUNDARY_IS.map((step) => (
                    <li className="about-method-card" key={step.index}>
                      <span className="about-method-index">{step.index}</span>
                      <div>
                        <b>{step.label}</b>
                        <h3>{step.title}</h3>
                        <p>{step.body}</p>
                      </div>
                    </li>
                  ))}
                </ol>

                <aside className="about-rigour-panel" aria-label="What this project is not">
                  <header>
                    <span>NOT</span>
                    <strong>{BOUNDARY_IS_NOT.length} EXCLUSIONS</strong>
                  </header>
                  <div className="about-rigour-list">
                    {BOUNDARY_IS_NOT.map((item, index) => (
                      <article key={item}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <div>
                          <b>{item}</b>
                        </div>
                      </article>
                    ))}
                  </div>
                </aside>
              </div>
            </section>

            <section className="about-research-board" aria-labelledby="about-method-title">
              <header className="about-research-head">
                <div>
                  <span className="tiny-label">RESEARCH METHOD / AUDIT PROTOCOL</span>
                  <h2 id="about-method-title">From public source to inspectable record</h2>
                </div>
                <p>
                  The archive documents how supernatural humanoid figures appear in public texts. It evaluates provenance and metadata quality; it does not test whether the reported phenomenon is real.
                </p>
              </header>

              <div className="about-method-layout">
                <ol className="about-method-sequence">
                  {METHOD_STEPS.map((step) => (
                    <li className="about-method-card" key={step.index}>
                      <span className="about-method-index">{step.index}</span>
                      <div>
                        <b>{step.label}</b>
                        <h3>{step.title}</h3>
                        <p>{step.body}</p>
                      </div>
                    </li>
                  ))}
                </ol>

                <aside className="about-rigour-panel" aria-label="Academic rigour checks">
                  <header>
                    <span>ACADEMIC RIGOUR</span>
                    <strong>04 CHECKS</strong>
                  </header>
                  <div className="about-rigour-list">
                    {RIGOUR_CHECKS.map((check, index) => (
                      <article key={check.label}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <div>
                          <b>{check.label}</b>
                          <p>{check.value}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                  <p className="about-rigour-note">
                    PUBLIC SOURCE EXISTS <strong>!=</strong> SUPERNATURAL CLAIM VERIFIED
                  </p>
                </aside>
              </div>

              <div className="about-typology" aria-label="Record type distribution">
                <header>
                  <span>RECORD TYPOLOGY</span>
                  <small>accepted public records by research classification</small>
                </header>
                <div className="about-typology-grid">
                  {recordTypeRows.map((row, index) => (
                    <article key={row.label}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <b>{row.label}</b>
                      <strong>{row.value}</strong>
                      <i
                        className="about-typology-bar"
                        style={{ "--share": row.share } as CSSProperties}
                        aria-hidden="true"
                      />
                    </article>
                  ))}
                </div>
              </div>
            </section>

            <details className="about-research-board about-collapsible" aria-labelledby="about-model-title">
              <summary className="about-research-head">
                <div>
                  <div className="about-collapsible-head-row">
                    <span className="tiny-label">DATA MODEL / SOURCE-CHAIN ARCHITECTURE</span>
                    <span className="about-collapsible-toggle" aria-hidden="true">
                      <span className="is-closed-label">+ EXPAND</span>
                      <span className="is-open-label">− COLLAPSE</span>
                    </span>
                  </div>
                  <h2 id="about-model-title">From a printed name to a reviewable record.</h2>
                </div>
                <p>
                  The archive separates what a source literally says from how it is analytically classified. Four normalized layers carry that separation end to end.
                </p>
              </summary>

              <div className="about-method-layout">
                <ol className="about-method-sequence">
                  {DATA_MODEL_STEPS.map((step) => (
                    <li className="about-method-card" key={step.index}>
                      <span className="about-method-index">{step.index}</span>
                      <div>
                        <b>{step.label}</b>
                        <h3>{step.title}</h3>
                        <p>{step.body}</p>
                      </div>
                    </li>
                  ))}
                </ol>

                <aside className="about-rigour-panel" aria-label="Object model notes">
                  <header>
                    <span>OBJECT MODEL</span>
                    <strong>{DATA_MODEL_NOTES.length} NOTES</strong>
                  </header>
                  <div className="about-rigour-list">
                    {DATA_MODEL_NOTES.map((note, index) => (
                      <article key={note.label}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <div>
                          <b>{note.label}</b>
                          <p>{note.value}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                </aside>
              </div>
            </details>

            <details className="about-research-board about-collapsible" aria-labelledby="about-source-standards-title">
              <summary className="about-research-head">
                <div>
                  <div className="about-collapsible-head-row">
                    <span className="tiny-label">SOURCE STANDARDS / ADMISSION LADDER</span>
                    <span className="about-collapsible-toggle" aria-hidden="true">
                      <span className="is-closed-label">+ EXPAND</span>
                      <span className="is-open-label">− COLLAPSE</span>
                    </span>
                  </div>
                  <h2 id="about-source-standards-title">Not every public mention is treated the same.</h2>
                </div>
                <p>
                  Sources are graded before a record is admitted. Five tiers set evidentiary strength; a separate four-stage ladder decides whether something is treated as evidence at all.
                </p>
              </summary>

              <div className="about-method-layout">
                <ol className="about-method-sequence">
                  {SOURCE_TIERS.map((tier) => (
                    <li className="about-method-card" key={tier.index}>
                      <span className="about-method-index">{tier.index}</span>
                      <div>
                        <b>{tier.label}</b>
                        <h3>{tier.title}</h3>
                        <p>{tier.body}</p>
                      </div>
                    </li>
                  ))}
                </ol>

                <aside className="about-rigour-panel" aria-label="Admission ladder">
                  <header>
                    <span>ADMISSION LADDER</span>
                    <strong>{ADMISSION_LADDER.length} STAGES</strong>
                  </header>
                  <div className="about-rigour-list">
                    {ADMISSION_LADDER.map((stage, index) => (
                      <article key={stage.label}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <div>
                          <b>{stage.label}</b>
                          <p>{stage.value}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                </aside>
              </div>
            </details>

            <section className="about-research-board" aria-labelledby="about-ethics-title">
              <header className="about-research-head">
                <div>
                  <span className="tiny-label">ETHICS / CULTURAL SENSITIVITY</span>
                  <h2 id="about-ethics-title">Publicly discoverable is not the same as publicly reproducible.</h2>
                </div>
                <p>
                  These rules govern every record before it is admitted, not only ones that look sensitive on the surface.
                </p>
              </header>

              <div className="about-method-layout">
                <div className="about-prose">
                  {ETHICS_PARAGRAPHS.map((paragraph) => (
                    <p key={paragraph.slice(0, 24)}>{paragraph}</p>
                  ))}
                </div>

                <aside className="about-rigour-panel" aria-label="Display states">
                  <header>
                    <span>DISPLAY STATES</span>
                    <strong>{DISPLAY_STATES.length} STATES</strong>
                  </header>
                  <div className="about-rigour-list">
                    {DISPLAY_STATES.map((state, index) => (
                      <article key={state.label}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <div>
                          <b>{state.label}</b>
                          <p>{state.value}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                </aside>
              </div>
            </section>

            <details className="about-research-board about-collapsible" aria-labelledby="about-contribution-title">
              <summary className="about-research-head">
                <div>
                  <div className="about-collapsible-head-row">
                    <span className="tiny-label">CONTRIBUTION / WHAT THIS ARCHIVE ADDS</span>
                    <span className="about-collapsible-toggle" aria-hidden="true">
                      <span className="is-closed-label">+ EXPAND</span>
                      <span className="is-open-label">− COLLAPSE</span>
                    </span>
                  </div>
                  <h2 id="about-contribution-title">Three choices this archive makes differently.</h2>
                </div>
                <p>
                  None of this is unique to any one record. It is in how the whole corpus is modelled, curated, and exposed.
                </p>
              </summary>

              <div className="about-method-layout">
                <ol className="about-method-sequence">
                  {CONTRIBUTION_POINTS.map((point) => (
                    <li className="about-method-card" key={point.index}>
                      <span className="about-method-index">{point.index}</span>
                      <div>
                        <b>{point.label}</b>
                        <h3>{point.title}</h3>
                        <p>{point.body}</p>
                      </div>
                    </li>
                  ))}
                </ol>

                <aside className="about-rigour-panel" aria-label="Research thread">
                  <header>
                    <span>RESEARCH THREAD</span>
                    <strong>1 NOTE</strong>
                  </header>
                  <div className="about-rigour-list">
                    <article>
                      <span>01</span>
                      <div>
                        <b>{RESEARCH_THREAD_NOTE.label}</b>
                        <p>{RESEARCH_THREAD_NOTE.value}</p>
                      </div>
                    </article>
                  </div>
                </aside>
              </div>
            </details>

            <details className="about-research-board about-collapsible" aria-labelledby="about-reference-title">
              <summary className="about-research-head">
                <div>
                  <div className="about-collapsible-head-row">
                    <span className="tiny-label">REFERENCE / GLOSSARY AND REVISION</span>
                    <span className="about-collapsible-toggle" aria-hidden="true">
                      <span className="is-closed-label">+ EXPAND</span>
                      <span className="is-open-label">− COLLAPSE</span>
                    </span>
                  </div>
                  <h2 id="about-reference-title">Terms used on this page, and where the numbers come from.</h2>
                </div>
                <p>
                  Every count on this page is read from the export below, not typed in by hand.
                </p>
              </summary>

              <div className="about-method-layout">
                <dl className="about-glossary-list" aria-label="Glossary of terms used on this page">
                  {GLOSSARY_TERMS.map((entry) => (
                    <div key={entry.term}>
                      <dt>{entry.term}</dt>
                      <dd>{entry.body}</dd>
                    </div>
                  ))}
                </dl>

                <aside className="about-rigour-panel" aria-label="Data version">
                  <header>
                    <span>DATA VERSION</span>
                    <strong>LIVE EXPORT</strong>
                  </header>
                  <dl className="about-glossary-list">
                    <div>
                      <dt>EXPORT CONTRACT</dt>
                      <dd>{data.schema_version}</dd>
                    </div>
                    <div>
                      <dt>EXPORT GENERATED</dt>
                      <dd>{exportDate}</dd>
                    </div>
                  </dl>
                </aside>
              </div>
            </details>

            <section className="about-citation-panel" aria-labelledby="about-citation-title">
              <header className="about-citation-head">
                <div>
                  <span className="tiny-label">CITATION / REPRODUCIBLE ATTRIBUTION</span>
                  <h2 id="about-citation-title">Cite the archive, then cite the source.</h2>
                </div>
                <p>
                  Use one project citation for the aggregation and coding layer. When discussing an individual record,
                  also cite its permanent AusFigures URL and the original public source shown on that record page.
                </p>
              </header>
              <CitationSamples samples={citationSamples} />
              <p className="about-citation-note">
                No DOI is assigned to this live export. Original-source rights, access conditions, and culturally
                specific context continue to apply.
              </p>
            </section>

            <section className="about-repository-panel" aria-labelledby="about-repository-title">
              <span className="about-repository-index" aria-hidden="true">GIT / 01</span>
              <div className="about-repository-copy">
                <span>GITHUB / PUBLIC PROJECT REPOSITORY</span>
                <h2 id="about-repository-title">Inspect the project behind the interface.</h2>
                <p>
                  The repository is the technical companion to this public display: source code, data policies, audit scripts, citation guidance, and revision history remain available for inspection and reuse.
                </p>
              </div>
              <dl className="about-repository-meta">
                <div>
                  <dt>HOST</dt>
                  <dd>github.com</dd>
                </div>
                <div>
                  <dt>PROJECT</dt>
                  <dd>australian-humanoid-supernatural-texts</dd>
                </div>
                <div>
                  <dt>ACCESS</dt>
                  <dd>public research repository</dd>
                </div>
              </dl>
              <a href={siteConfig.repositoryUrl} target="_blank" rel="noreferrer">
                <span>VIEW GITHUB REPOSITORY</span>
                <b aria-hidden="true">↗</b>
              </a>
            </section>
          </div>
        </section>
        <div className="terminal-footer-controls">
          <DisplayControls />
          <div className="external-control-dock" aria-label="Fixed external controls">
            <Link className="dock-button about-button active" href="/about" aria-current="page">
              About
            </Link>
            <Link className="dock-button source-button" href="/source">
              Source
            </Link>
            <Link className="dock-button view-cycle-button" href="/dashboard">
              Dashboard
            </Link>
          </div>
        </div>
      </div>
      </main>
    </>
  );
}

async function loadAboutData(): Promise<FrontendData> {
  if (FRONTEND_DATA_URL.startsWith("/")) {
    const dataPath = path.join(process.cwd(), "public", FRONTEND_DATA_URL.replace(/^\/+/, ""));
    return JSON.parse(await readFile(dataPath, "utf8")) as FrontendData;
  }

  const response = await fetch(FRONTEND_DATA_URL, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`About data request failed: ${response.status}`);
  }
  return response.json() as Promise<FrontendData>;
}

function buildStatusCells(sourceData: FrontendData) {
  const summary = sourceData.summary;
  const sourceMetrics = buildSourceRegistryData(sourceData).metrics;
  const dateSpan = summary.earliest_year && summary.latest_year ? `${summary.earliest_year}-${summary.latest_year}` : null;
  return [
    { label: "PUBLIC RECORDS", value: numberFormat(summary.record_count || sourceData.records.length) },
    { label: "MAPPED RECORDS", value: numberFormat(summary.mapped_record_count || sourceData.map_flags?.length || sourceData.map_points.length) },
    { label: "SOURCE ORGS", value: numberFormat(sourceMetrics.sourceOrgs) },
    { label: "SOURCE TYPES", value: numberFormat(sourceMetrics.sourceTypes) },
    dateSpan ? { label: "DATE SPAN", value: dateSpan } : null,
  ].filter((cell): cell is { label: string; value: string } => Boolean(cell));
}

function buildRecordTypeRows(sourceData: FrontendData) {
  const labels: Record<string, string> = {
    cryptid_style_apeman: "Encounter accounts",
    apparition_account: "Apparition records",
    ghost_legend: "Ghost legends",
    local_legend: "Local legends",
    traditional_narrative: "Traditional narratives",
    spirit_person_narrative: "Spirit-person narratives",
    retelling_or_adaptation: "Retellings",
  };
  const rows = Object.entries(labels)
    .map(([key, label]) => ({
      label,
      value: sourceData.summary.ontology_counts[key] ?? 0,
    }))
    .filter((row) => row.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);
  const peak = Math.max(1, ...rows.map((row) => row.value));
  // share drives a CSS-only segmented bar; computed here on the server so the
  // chart costs zero client JavaScript.
  return rows.map((row) => ({
    label: row.label,
    value: numberFormat(row.value),
    share: Number((row.value / peak).toFixed(3)),
  }));
}

function numberFormat(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}
