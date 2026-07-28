import Link from "next/link";
import {
  ArchivePublicationPage,
  ArchiveRecordList,
  PublicationSection,
} from "@/components/archive-publication";
import {
  indexableRecords,
  loadArchiveData,
  recordsForIndexPage,
  recordsIndexPageCount,
} from "@/lib/archive-catalog";
import { archiveBreadcrumbJsonLd } from "@/lib/archive-metadata";
import { recordPath, recordsPagePath } from "@/lib/archive-routing";
import { SITE, absoluteUrl, siteConfig } from "@/lib/site";

export async function RecordsIndexPage({ page }: { page: number }) {
  const data = await loadArchiveData();
  const totalPages = recordsIndexPageCount(data);
  const records = recordsForIndexPage(data, page);
  const totalRecords = indexableRecords(data).length;
  const pagePath = recordsPagePath(page);

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${absoluteUrl(pagePath)}#webpage`,
        name: page === 1 ? "AusFigures Public Records" : `AusFigures Public Records — Page ${page}`,
        url: absoluteUrl(pagePath),
        description:
          "Search-ready public-text records in the AusFigures Australian supernatural humanoid archive.",
        isPartOf: {
          "@id": `${siteConfig.siteUrl}/#website`,
        },
        mainEntity: {
          "@type": "ItemList",
          numberOfItems: records.length,
          itemListElement: records.map((record, index) => ({
            "@type": "ListItem",
            position: (page - 1) * 100 + index + 1,
            name: record.title,
            url: absoluteUrl(recordPath(record)),
          })),
        },
      },
      archiveBreadcrumbJsonLd([
        { name: SITE.name, path: "/" },
        { name: "Public records", path: "/records" },
        ...(page > 1 ? [{ name: `Page ${page}`, path: pagePath }] : []),
      ]),
    ],
  };

  return (
    <ArchivePublicationPage
      eyebrow="RECORD INDEX"
      title={page === 1 ? "Search-ready public records" : `Public records — page ${page}`}
      intro="Browse source-grounded records across hairy and wild-person accounts, ghosts and apparitions, spirit-person narratives, giants and ogres, belief descriptions, encounters, legends, and retellings."
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/records", label: "Records" },
        ...(page > 1 ? [{ href: pagePath, label: `Page ${page}` }] : []),
      ]}
      stats={[
        { label: "Search-ready records", value: totalRecords },
        { label: "Page", value: `${page} / ${totalPages}` },
        { label: "Records on page", value: records.length },
        { label: "Archive generated", value: data.generated_at.slice(0, 10) },
      ]}
      notice="Only records that pass the public-page and search-index review gate appear in this index. Accepted records still awaiting indexing or sensitivity review remain outside the sitemap."
    >
      <script
        id={`records-page-${page}-structured-data`}
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }}
      />
      <PublicationSection title={`Records ${(page - 1) * 100 + 1}–${(page - 1) * 100 + records.length}`}>
        <ArchiveRecordList records={records} />
      </PublicationSection>
      <nav className="publication-pagination" aria-label="Record index pagination">
        {page > 1 ? <Link href={recordsPagePath(page - 1)}>← Previous</Link> : <span />}
        <Link href="/records">Record index</Link>
        {page < totalPages ? <Link href={recordsPagePath(page + 1)}>Next →</Link> : <span />}
      </nav>
    </ArchivePublicationPage>
  );
}
