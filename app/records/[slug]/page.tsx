import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import {
  ArchivePublicationPage,
  ArchiveRecordList,
  PublicationSection,
  RecordDefinitionList,
  compactText,
} from "@/components/archive-publication";
import {
  archiveRecordPolicy,
  loadArchiveData,
  publicRecordPages,
  recordByRouteSlug,
  relatedRecords,
} from "@/lib/archive-catalog";
import { archiveBreadcrumbJsonLd, archivePageMetadata } from "@/lib/archive-metadata";
import {
  labelPath,
  narrativeTypeName,
  narrativeTypePath,
  recordPath,
  recordRouteSlug,
  sourcePath,
} from "@/lib/archive-routing";
import { SITE, absoluteUrl, siteConfig } from "@/lib/site";

type RecordPageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  return publicRecordPages(data).map((record) => ({
    slug: recordRouteSlug(record),
  }));
}

export async function generateMetadata({ params }: RecordPageProps): Promise<Metadata> {
  const { slug } = await params;
  const data = await loadArchiveData();
  const record = recordByRouteSlug(data, slug);
  if (!record) {
    return {};
  }
  const policy = archiveRecordPolicy(record);
  const title = `${record.title} — Public-Text Record`;
  const description = compactText(
    record.snippet ||
      `${record.title} is a source-grounded public-text record in the AusFigures Australian supernatural humanoid archive.`,
    158,
  );
  return archivePageMetadata({
    title,
    description,
    path: recordPath(record),
    index: policy.indexEligible,
    keywords: [
      record.canonical_figure_guess || record.canonical_figure || "",
      narrativeTypeName(record.ontology_code || record.genre || "unspecified"),
      record.state_territory || "",
      record.source_name || "",
    ].filter(Boolean),
  });
}

export default async function RecordPage({ params }: RecordPageProps) {
  const { slug } = await params;
  const data = await loadArchiveData();
  const record = recordByRouteSlug(data, slug);
  if (!record) {
    notFound();
  }
  if (slug !== recordRouteSlug(record)) {
    permanentRedirect(recordPath(record));
  }

  const policy = archiveRecordPolicy(record);
  const related = relatedRecords(data, record);
  const label = record.canonical_figure_guess || record.canonical_figure;
  const narrativeCode = record.ontology_code || record.genre;
  const pageUrl = absoluteUrl(recordPath(record));
  const description = compactText(
    record.snippet ||
      `${record.title} is a source-grounded public-text record in the AusFigures archive.`,
    300,
  );
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "ArchiveComponent",
        "@id": `${pageUrl}#record`,
        name: record.title,
        url: pageUrl,
        description,
        identifier: String(record.record_id),
        datePublished: record.date_published || (record.year ? String(record.year) : undefined),
        dateModified: data.generated_at,
        inLanguage: "en-AU",
        isPartOf: {
          "@id": `${siteConfig.siteUrl}/#dataset`,
        },
        archivedAt: {
          "@type": "WebPage",
          url: record.url,
          name: record.source_name || undefined,
        },
        about: [label, narrativeCode, record.state_territory].filter(Boolean),
      },
      archiveBreadcrumbJsonLd([
        { name: SITE.name, path: "/" },
        { name: "Public records", path: "/records" },
        { name: record.title || `Record ${record.record_id}`, path: recordPath(record) },
      ]),
    ],
  };

  return (
    <ArchivePublicationPage
      eyebrow="PUBLIC-TEXT RECORD"
      title={record.title || `Record ${record.record_id}`}
      intro={description}
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/records", label: "Records" },
        { href: recordPath(record), label: `#${record.record_id}` },
      ]}
      stats={[
        { label: "Record ID", value: record.record_id },
        { label: "Year", value: record.year ?? "Undated" },
        { label: "Source", value: record.source_name || "Unspecified" },
        { label: "Index status", value: policy.indexEligible ? "Public search-ready" : "Review-only" },
      ]}
      notice={
        policy.indexEligible
          ? "This page records what a public source contains. It is not verification of the supernatural claim described by that source."
          : "This accepted public record remains outside the search sitemap while its indexing or cultural-sensitivity review is incomplete."
      }
    >
      <script
        id={`record-${record.record_id}-structured-data`}
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }}
      />

      <PublicationSection title="Record context">
        <RecordDefinitionList record={record} />
      </PublicationSection>

      {record.snippet ? (
        <PublicationSection title="Source-grounded excerpt">
          <blockquote className="publication-excerpt">{record.snippet}</blockquote>
          <p className="publication-caveat">
            The excerpt is presented as public-source context. Terminology belongs to the cited source and may be historical,
            contested, culturally specific, or outdated.
          </p>
        </PublicationSection>
      ) : null}

      <PublicationSection title="Browse this record">
        <div className="publication-link-row">
          {narrativeCode ? (
            <Link href={narrativeTypePath(narrativeCode)}>
              Narrative type: {narrativeTypeName(narrativeCode)}
            </Link>
          ) : null}
          {label ? <Link href={labelPath(label)}>Public-text label: {label}</Link> : null}
          {record.source_name ? (
            <Link href={sourcePath(record.source_id, record.source_name)}>Source: {record.source_name}</Link>
          ) : null}
          <a href={record.url || "#"} rel="noopener noreferrer" target="_blank">
            Open original public source
          </a>
        </div>
      </PublicationSection>

      <PublicationSection title="Related public records">
        <ArchiveRecordList records={related} />
      </PublicationSection>
    </ArchivePublicationPage>
  );
}
