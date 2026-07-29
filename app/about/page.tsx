import { readFile } from "node:fs/promises";
import path from "node:path";
import Link from "next/link";
import { AboutAmbientMotion } from "@/components/about/about-ambient-motion";
import { CitationSamples } from "@/components/citation-samples";
import { DisplayControls } from "@/components/display-controls";
import { MobileArchiveControls } from "@/components/mobile-archive";
import { RouteStructuredData } from "@/components/route-structured-data";
import { FRONTEND_DATA_URL } from "@/lib/frontend-data";
import { metadataForRoute, siteConfig } from "@/lib/site";
import { buildProjectCitations } from "@/lib/citations";
import { buildSourceRegistryData } from "@/lib/source-view-data";
import type { FrontendData } from "@/lib/types";

export const metadata = metadataForRoute("/about");

const METHOD_STEPS = [
  {
    index: "01",
    label: "SOURCE DISCOVERY",
    title: "Find a public trace",
    body:
      "Search public archives, libraries, newspapers, digitised books, repositories, institutional pages, and community-controlled public sources. Aggregators and tourism pages can lead to a source, but are not admitted as primary support on their own.",
  },
  {
    index: "02",
    label: "RECORD ADMISSION",
    title: "Preserve provenance",
    body:
      "Admit a record only when a public source or public metadata item can be cited. Keep source organisation, publication role, date, record type, and publicness visible so the record can be checked or revised later.",
  },
  {
    index: "03",
    label: "CLASSIFICATION",
    title: "Keep research layers separate",
    body:
      "Code the printed figure or descriptive label, narrative type, source family, period, and place role separately. A shared archive category does not make culturally distinct beings, traditions, or claims equivalent.",
  },
  {
    index: "04",
    label: "LOCATION REVIEW",
    title: "Map only reviewed evidence",
    body:
      "Publish one display flag only when a record has usable location evidence. Narrative geography, alleged event geography, source location, and broad regional association remain distinct and are never presented as habitat or proof.",
  },
] as const;

const RIGOUR_CHECKS = [
  {
    label: "PROVENANCE",
    value: "Source, public role, record type, and citation path stay inspectable.",
  },
  {
    label: "LAYER SEPARATION",
    value: "Public records, mapped records, metadata-only items, and research leads are not interchangeable counts.",
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

export default async function AboutPage() {
  const data = await loadAboutData();
  const statusCells = buildStatusCells(data);
  const recordTypeRows = buildRecordTypeRows(data);
  const citationSamples = buildProjectCitations(data.generated_at.slice(0, 10));

  return (
    <main className="terminal-shell">
      <div className="noise-layer" aria-hidden="true" />
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
                <h1 className="about-desktop-title">AUSTRALIAN HUMANOID SUPERNATURAL TEXTS</h1>
                <p className="about-subtitle">Public-text archive and research display system</p>
                <p>
                  This project is a public-text archive for tracing how humanoid or humanoid-adjacent supernatural figures appear in Australian public sources.
                </p>
                <p>
                  It records published accounts, apparition narratives, local legends, traditional and spirit-person narratives, retellings, and related discourse as source-grounded public records. Inclusion means that a public source or public metadata record exists; it does not verify the supernatural claim described by that source.
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
                    </article>
                  ))}
                </div>
              </div>
            </section>

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
                No DOI is asserted for this live export. Original-source rights, access conditions, and culturally
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
        <MobileArchiveControls view="about" />
      </div>
    </main>
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
  return Object.entries(labels)
    .map(([key, label]) => ({
      label,
      value: sourceData.summary.ontology_counts[key] ?? 0,
    }))
    .filter((row) => row.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 6)
    .map((row) => ({ ...row, value: numberFormat(row.value) }));
}

function numberFormat(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}
