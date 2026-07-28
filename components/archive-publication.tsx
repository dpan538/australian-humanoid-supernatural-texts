import Link from "next/link";
import { DisplayControls } from "@/components/display-controls";
import {
  humanizeArchiveCode,
  narrativeTypeName,
  recordPath,
} from "@/lib/archive-routing";
import { SITE, absoluteUrl, siteConfig } from "@/lib/site";
import type { RecordItem } from "@/lib/types";

export type ArchiveBreadcrumb = {
  href: string;
  label: string;
};

export type ArchiveCollectionCard = {
  href: string;
  title: string;
  count: number;
  description?: string;
};

export function ArchivePublicationPage({
  eyebrow,
  title,
  intro,
  breadcrumbs,
  stats = [],
  notice,
  children,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  breadcrumbs: ArchiveBreadcrumb[];
  stats?: Array<{ label: string; value: string | number }>;
  notice?: string;
  children: React.ReactNode;
}) {
  return (
    <main className="terminal-shell publication-shell">
      <div className="noise-layer" aria-hidden="true" />
      <div className="terminal-stage publication-frame">
        <header className="publication-console-bar">
          <Link href="/">
            <strong>AUSFIGURES</strong>
            <span>PUBLIC-TEXT ARCHIVE</span>
          </Link>
          <span>ARCHIVE INDEX MODE</span>
          <nav aria-label="Archive index navigation">
            <Link href="/map">MAP</Link>
            <Link href="/records">RECORDS</Link>
            <Link href="/narrative-types">TYPES</Link>
            <Link href="/sources">SOURCES</Link>
            <Link href="/about">METHOD</Link>
          </nav>
        </header>
        <nav className="publication-breadcrumbs" aria-label="Breadcrumb">
          {breadcrumbs.map((item, index) => (
            <span key={item.href}>
              {index > 0 ? <i aria-hidden="true">/</i> : null}
              <Link href={item.href}>{item.label}</Link>
            </span>
          ))}
        </nav>
        <header className="publication-hero">
          <span>{eyebrow}</span>
          <h1>{title}</h1>
          <p>{intro}</p>
        </header>
        {stats.length ? (
          <dl className="publication-stats">
            {stats.map((stat) => (
              <div key={stat.label}>
                <dt>{stat.label}</dt>
                <dd>{typeof stat.value === "number" ? formatNumber(stat.value) : stat.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        <aside className="publication-light-guide" aria-label="Archive reading guide">
          <strong>How to read this public-text archive</strong>
          <p>
            Browse individual records or move across narrative types, printed labels, sources, places, and periods.
            Yowie, wild-man, ghost, apparition, and related terms are preserved as source labels inside the broader
            analytical category of supernatural humanoids; a recorded mention is not treated as proof of a claim.
          </p>
        </aside>
        {notice ? <p className="publication-notice">{notice}</p> : null}
        <div className="publication-content">{children}</div>
        <footer className="publication-footer">
          <p>Public source exists does not mean a supernatural claim is verified.</p>
          <nav aria-label="Archive footer navigation">
            <Link href="/records">Records</Link>
            <Link href="/topics">Topics</Link>
            <Link href="/data">Data</Link>
            <Link href="/cite">Cite</Link>
          </nav>
        </footer>
        <div className="terminal-footer-controls publication-display-controls">
          <DisplayControls />
        </div>
      </div>
    </main>
  );
}

export function ArchiveRecordList({
  records,
  emptyMessage = "No index-ready public records are available in this collection.",
}: {
  records: RecordItem[];
  emptyMessage?: string;
}) {
  if (!records.length) {
    return <p className="publication-empty">{emptyMessage}</p>;
  }

  return (
    <ol className="publication-record-list">
      {records.map((record) => (
        <li key={record.record_id}>
          <Link href={recordPath(record)}>
            <span className="record-list-heading">
              <strong>{record.title}</strong>
              <b>#{record.record_id}</b>
            </span>
            <span className="record-list-meta">
              {[
                record.year ?? "Undated",
                record.source_name,
                record.state_territory,
                narrativeTypeName(record.ontology_code ?? record.genre ?? "unspecified"),
              ]
                .filter(Boolean)
                .join(" / ")}
            </span>
            {record.snippet ? <span className="record-list-snippet">{compactText(record.snippet, 220)}</span> : null}
          </Link>
        </li>
      ))}
    </ol>
  );
}

export function ArchiveCollectionGrid({ items }: { items: ArchiveCollectionCard[] }) {
  return (
    <div className="publication-collection-grid">
      {items.map((item) => (
        <Link href={item.href} key={item.href}>
          <span>
            <strong>{item.title}</strong>
            <b>{formatNumber(item.count)}</b>
          </span>
          {item.description ? <small>{item.description}</small> : null}
        </Link>
      ))}
    </div>
  );
}

export function ArchiveRecordCollectionPage({
  eyebrow,
  title,
  intro,
  path,
  parentHref,
  parentLabel,
  records,
  notice,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  path: string;
  parentHref: string;
  parentLabel: string;
  records: RecordItem[];
  notice?: string;
}) {
  const sourceCount = new Set(records.map((record) => record.source_id)).size;
  const states = new Set(records.map((record) => record.state_territory).filter(Boolean)).size;
  const datedYears = records
    .map((record) => record.year)
    .filter((year): year is number => typeof year === "number" && Number.isFinite(year));
  const earliest = datedYears.length ? Math.min(...datedYears) : null;
  const latest = datedYears.length ? Math.max(...datedYears) : null;
  const preview = records.slice(0, 60);
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${absoluteUrl(path)}#webpage`,
        name: `${title} | ${SITE.name}`,
        url: absoluteUrl(path),
        description: intro,
        isPartOf: {
          "@id": `${siteConfig.siteUrl}/#website`,
        },
        mainEntity: {
          "@type": "ItemList",
          numberOfItems: records.length,
          itemListElement: preview.map((record, index) => ({
            "@type": "ListItem",
            position: index + 1,
            name: record.title,
            url: absoluteUrl(recordPath(record)),
          })),
        },
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: SITE.name, item: siteConfig.siteUrl },
          { "@type": "ListItem", position: 2, name: parentLabel, item: absoluteUrl(parentHref) },
          { "@type": "ListItem", position: 3, name: title, item: absoluteUrl(path) },
        ],
      },
    ],
  };

  return (
    <ArchivePublicationPage
      eyebrow={eyebrow}
      title={title}
      intro={intro}
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: parentHref, label: parentLabel },
        { href: path, label: title },
      ]}
      stats={[
        { label: "Search-ready records", value: records.length },
        { label: "Public sources", value: sourceCount },
        { label: "States / territories", value: states },
        { label: "Dated span", value: earliest && latest ? `${earliest}–${latest}` : "Undated" },
      ]}
      notice={notice}
    >
      <script
        id={`${path.replace(/[^a-z0-9]+/gi, "-")}-structured-data`}
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }}
      />
      <PublicationSection title={records.length > preview.length ? `Representative records — first ${preview.length}` : "Public records"}>
        <ArchiveRecordList records={preview} />
      </PublicationSection>
      {records.length > preview.length ? (
        <p className="publication-more-note">
          This collection contains {formatNumber(records.length)} search-ready records. The complete record set remains
          discoverable through the paginated <Link href="/records">public record index</Link>.
        </p>
      ) : null}
    </ArchivePublicationPage>
  );
}

export function RecordDefinitionList({ record }: { record: RecordItem }) {
  const rows = [
    ["Record ID", String(record.record_id)],
    ["Source", record.source_name],
    ["Publication", record.publication],
    ["Author", record.author],
    ["Published", record.date_published || (record.year ? String(record.year) : null)],
    ["Narrative type", narrativeTypeName(record.ontology_code ?? record.genre ?? "unspecified")],
    ["Public-text label", record.figure_name_as_printed || record.canonical_figure_guess || record.canonical_figure],
    ["Archive period", humanizeArchiveCode(record.date_band)],
    ["Location", record.location_summary],
    ["State or territory", record.state_territory],
    ["Source voice", humanizeArchiveCode(record.source_voice)],
    ["Publicness", humanizeArchiveCode(record.publicness_code || record.publicness_level)],
  ].filter((row): row is [string, string] => Boolean(row[1]));

  return (
    <dl className="publication-definition-list">
      {rows.map(([term, value]) => (
        <div key={term}>
          <dt>{term}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function PublicationSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="publication-section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function compactText(value: string, limit = 170) {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trimEnd()}…` : text;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}
