import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArchiveRecordCollectionPage } from "@/components/archive-publication";
import { loadArchiveData, periodGroups } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { archiveSlug, periodPath } from "@/lib/archive-routing";

type PeriodPageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  return periodGroups(data).map((group) => ({ slug: archiveSlug(group.key) }));
}

export async function generateMetadata({ params }: PeriodPageProps): Promise<Metadata> {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = periodGroups(data).find((item) => archiveSlug(item.key) === slug);
  if (!group) {
    return {};
  }
  return archivePageMetadata({
    title: `${group.label} Australian Supernatural Public Texts`,
    description: `Browse ${group.records.length} search-ready AusFigures supernatural humanoid public-text records from ${group.label}.`,
    path: periodPath(group.key),
    keywords: [`Australian supernatural records ${group.label}`, `${group.label} folklore public texts`],
  });
}

export default async function PeriodDetailPage({ params }: PeriodPageProps) {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = periodGroups(data).find((item) => archiveSlug(item.key) === slug);
  if (!group) {
    notFound();
  }
  return (
    <ArchiveRecordCollectionPage
      eyebrow="SOURCE PERIOD"
      title={group.label}
      intro={`This collection groups search-ready public-text records assigned to ${group.label}. Counts reflect source survival, collection coverage, publication patterns, and archive coding rather than real-world supernatural frequency.`}
      path={periodPath(group.key)}
      parentHref="/periods"
      parentLabel="Periods"
      records={group.records}
    />
  );
}
