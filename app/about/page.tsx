import Link from "next/link";
import frontendData from "@/public/data/frontend-data.json";
import { AboutAmbientMotion } from "@/components/about/about-ambient-motion";
import { DisplayControls } from "@/components/display-controls";
import { MobileArchiveControls } from "@/components/mobile-archive";
import { RouteStructuredData } from "@/components/route-structured-data";
import { metadataForRoute } from "@/lib/site";
import type { FrontendData } from "@/lib/types";

const data = frontendData as FrontendData;

export const metadata = metadataForRoute("/about");

export default function AboutPage() {
  const statusCells = buildStatusCells(data);
  const recordTypeRows = buildRecordTypeRows(data);

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

            <section className="about-grid" aria-label="Research display modules">
              <AboutModule
                kicker="WHAT THIS ARCHIVE IS"
                title="Documented public texts, not proof claims"
                body="The archive treats each entry as a documented public text or source-grounded narrative unit. Records are organised by source family, narrative type, period, publicness, and available location evidence so later research can separate reported encounters, retellings, heritage discourse, catalogue metadata, and contextual material."
                mobileBody="A public-text archive of source-grounded supernatural humanoid records. Inclusion means a public source exists; it does not verify the claim."
              />

              <details className="about-module about-model-module about-accordion-module" aria-label="Archive model">
                <summary className="about-module-head">
                  <span>ARCHIVE MODEL</span>
                  <i aria-hidden="true" />
                </summary>
                <h2 className="about-desktop-detail">Source item to research record</h2>
                <p className="about-mobile-detail">Source item to public record to narrative type to location role. Each step stays auditable.</p>
                <div className="about-flow about-desktop-detail" aria-label="Archive model flow">
                  <svg viewBox="0 0 520 128" role="img" aria-label="Source item to public record to narrative type to location role">
                    <line className="about-flow-line" x1="68" y1="64" x2="182" y2="64" pathLength="1" />
                    <line className="about-flow-line" x1="250" y1="64" x2="364" y2="64" pathLength="1" />
                    <line className="about-flow-line" x1="432" y1="64" x2="492" y2="64" pathLength="1" />
                    <circle cx="44" cy="64" r="16" />
                    <circle cx="216" cy="64" r="16" />
                    <circle cx="398" cy="64" r="16" />
                    <circle cx="492" cy="64" r="10" />
                  </svg>
                  <div className="about-flow-labels">
                    <span>source item</span>
                    <span>public record</span>
                    <span>narrative type</span>
                    <span>location role</span>
                  </div>
                </div>
              </details>

              <details className="about-module about-record-types about-accordion-module" aria-label="Record types">
                <summary className="about-module-head">
                  <span>RECORD TYPES</span>
                  <i aria-hidden="true" />
                </summary>
                <h2 className="about-desktop-detail">Typed narrative surface</h2>
                <p className="about-mobile-detail">Record types separate encounters, apparitions, legends, traditional or spirit-person narratives, and retellings.</p>
                <div className="about-type-list about-desktop-detail">
                  {recordTypeRows.map((row) => (
                    <span key={row.label}>
                      <b>{row.label}</b>
                      <i aria-hidden="true" />
                      <strong>{row.value}</strong>
                    </span>
                  ))}
                </div>
              </details>

              <AboutModule
                kicker="MAP RULE"
                title="One verified location flag per mapped public record"
                body="Map points represent records with a verified display location. They indicate narrative geography, alleged event geography, or place association depending on the record type. They are not habitat maps, population maps, or proof of an underlying phenomenon."
                mobileBody="Map points are public display locations for records. They are not proof, habitats, or populations."
              />

              <AboutModule
                kicker="SOURCE POLICY"
                title="Public sources first"
                body="The project prioritises public archives, libraries, newspapers, digitised books, institutional pages, public repositories, and community-controlled public sources. Tourism pages and unsourced paranormal aggregators may be useful as discovery leads, but they are not treated as primary evidence without stronger source support."
                mobileBody="The archive prioritises public archives, libraries, newspapers, books, repositories, and institutional or community-controlled public sources."
              />

              <AboutModule
                kicker="ETHICS / SENSITIVITY"
                title="Public discoverability is not unrestricted permission"
                body="Records involving Aboriginal and Torres Strait Islander peoples, communities, or culturally specific figures require additional care around terminology, publicness, display mode, and source context. Sensitive public material may be summary-only or suppressed."
                mobileBody="Indigenous-related records require careful terminology, source voice, publicness, cultural sensitivity, and display mode."
              />
            </section>

            <section className="about-extension-panel" aria-label="Research extension">
              <div className="about-module-head">
                <span>RESEARCH EXTENSION</span>
                <i aria-hidden="true" />
              </div>
              <div>
                <h2>Designed for audit, revision, and extension</h2>
                <p>
                  The interface is designed as a research display rather than a final authority. Future work can add sources, revise classifications, improve location evidence, separate source items from narrative units, and audit sensitive records without treating the current corpus as complete or peer reviewed.
                </p>
              </div>
              <div className="about-raster" aria-hidden="true">
                {Array.from({ length: 15 }, (_, index) => (
                  <i className={index === 2 || index === 8 || index === 13 ? "about-raster-cell is-live" : "about-raster-cell"} key={index} />
                ))}
              </div>
            </section>

            <nav className="about-actions" aria-label="Archive views">
              <Link href="/map">MAP</Link>
              <Link href="/dashboard">DASHBOARD</Link>
              <Link href="/density">DENSITY</Link>
              <Link href="/source">SOURCE</Link>
              <Link href="/topics">TOPICS</Link>
            </nav>
          </div>
        </section>
        <div className="terminal-footer-controls">
          <DisplayControls />
        </div>
        <MobileArchiveControls view="about" />
      </div>
    </main>
  );
}

function AboutModule({ kicker, title, body, mobileBody }: { kicker: string; title: string; body: string; mobileBody?: string }) {
  return (
    <details className="about-module about-accordion-module">
      <summary className="about-module-head">
        <span>{kicker}</span>
        <i aria-hidden="true" />
      </summary>
      <h2 className="about-desktop-detail">{title}</h2>
      <p className="about-desktop-detail">{body}</p>
      <p className="about-mobile-detail">{mobileBody ?? body}</p>
    </details>
  );
}

function buildStatusCells(sourceData: FrontendData) {
  const summary = sourceData.summary;
  const sourceTypes = new Set(sourceData.sources.map((source) => source.source_type).filter(Boolean));
  const dateSpan = summary.earliest_year && summary.latest_year ? `${summary.earliest_year}-${summary.latest_year}` : null;
  return [
    { label: "PUBLIC RECORDS", value: numberFormat(summary.record_count || sourceData.records.length) },
    { label: "MAPPED RECORDS", value: numberFormat(summary.mapped_record_count || sourceData.map_flags?.length || sourceData.map_points.length) },
    { label: "SOURCE ORGS", value: numberFormat(summary.source_count || sourceData.sources.length) },
    { label: "SOURCE TYPES", value: numberFormat(sourceTypes.size) },
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
