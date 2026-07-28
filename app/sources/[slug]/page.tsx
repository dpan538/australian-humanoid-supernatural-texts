import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArchiveRecordCollectionPage } from "@/components/archive-publication";
import { loadArchiveData, sourceGroupByRouteSlug, sourceGroups } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { humanizeArchiveCode, sourcePath } from "@/lib/archive-routing";

type SourcePageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  return sourceGroups(data).map((group) => ({
    slug: sourcePath(group.sourceId, group.label).split("/").at(-1) as string,
  }));
}

export async function generateMetadata({ params }: SourcePageProps): Promise<Metadata> {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = sourceGroupByRouteSlug(data, slug);
  if (!group) {
    return {};
  }
  return archivePageMetadata({
    title: `${group.label} — Public Source Records`,
    description: `Browse ${group.records.length} search-ready AusFigures public-text records connected to ${group.label}.`,
    path: sourcePath(group.sourceId, group.label),
    index: group.records.length >= 2,
    keywords: [group.label, humanizeArchiveCode(group.source?.source_type || group.records[0]?.source_type)],
  });
}

export default async function SourceDetailPage({ params }: SourcePageProps) {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = sourceGroupByRouteSlug(data, slug);
  if (!group) {
    notFound();
  }
  const sourceType = humanizeArchiveCode(group.source?.source_type || group.records[0]?.source_type);
  return (
    <ArchiveRecordCollectionPage
      eyebrow="PUBLIC SOURCE"
      title={group.label}
      intro={`${group.label} contributes public ${sourceType.toLowerCase()} context represented in the AusFigures archive. This page links source-grounded records to their original public URLs and preserves provenance without implying institutional endorsement.`}
      path={sourcePath(group.sourceId, group.label)}
      parentHref="/sources"
      parentLabel="Sources"
      records={group.records}
      notice={
        group.records.length >= 2
          ? "The source collection is included for provenance and public-text discovery."
          : "This one-record source page is available for provenance but remains outside the search sitemap to avoid a thin collection page."
      }
    />
  );
}
