import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArchiveRecordCollectionPage } from "@/components/archive-publication";
import { labelGroups, loadArchiveData } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { archiveSlug, labelPath } from "@/lib/archive-routing";

type LabelPageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  return labelGroups(data).map((group) => ({ slug: archiveSlug(group.key) }));
}

export async function generateMetadata({ params }: LabelPageProps): Promise<Metadata> {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = labelGroups(data).find((item) => archiveSlug(item.key) === slug);
  if (!group) {
    return {};
  }
  return archivePageMetadata({
    title: `${group.label} in Australian Public Texts`,
    description: `Browse ${group.records.length} public-text records carrying the ${group.label} label in the AusFigures archive.`,
    path: labelPath(group.key),
    keywords: [group.label, `${group.label} Australia`, "Australian supernatural public texts"],
  });
}

export default async function LabelPage({ params }: LabelPageProps) {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = labelGroups(data).find((item) => archiveSlug(item.key) === slug);
  if (!group) {
    notFound();
  }
  return (
    <ArchiveRecordCollectionPage
      eyebrow="PUBLIC-TEXT LABEL"
      title={group.label}
      intro={`This page groups search-ready records carrying the label “${group.label}” in public source text or archive coding. It preserves a discovery term without treating the label as proof, a biological category, or a claim that distinct cultural traditions are interchangeable.`}
      path={labelPath(group.key)}
      parentHref="/labels"
      parentLabel="Labels"
      records={group.records}
      notice="Terminology belongs to the cited public sources and may be historical, contested, culturally specific, or outdated."
    />
  );
}
