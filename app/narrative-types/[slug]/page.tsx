import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArchiveRecordCollectionPage } from "@/components/archive-publication";
import { loadArchiveData, narrativeTypeGroups } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { archiveSlug, narrativeTypePath } from "@/lib/archive-routing";

type NarrativeTypePageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  return narrativeTypeGroups(data).map((group) => ({ slug: archiveSlug(group.key) }));
}

export async function generateMetadata({ params }: NarrativeTypePageProps): Promise<Metadata> {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = narrativeTypeGroups(data).find((item) => archiveSlug(item.key) === slug);
  if (!group) {
    return {};
  }
  return archivePageMetadata({
    title: `${group.label} in Australian Public Texts`,
    description: `Browse ${group.records.length} source-grounded ${group.label.toLowerCase()} in the AusFigures Australian supernatural humanoid public-text archive.`,
    path: narrativeTypePath(group.key),
    keywords: [group.label, `${group.label} Australia`, "Australian public-text archive"],
    social: {
      eyebrow: "NARRATIVE TYPE",
      metric: `${group.records.length.toLocaleString("en-AU")} records`,
      tone: "ink",
    },
  });
}

export default async function NarrativeTypePage({ params }: NarrativeTypePageProps) {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = narrativeTypeGroups(data).find((item) => archiveSlug(item.key) === slug);
  if (!group) {
    notFound();
  }
  return (
    <ArchiveRecordCollectionPage
      eyebrow="NARRATIVE TYPE"
      title={group.label}
      intro={`${group.label} are grouped here as a public-text classification across the AusFigures corpus. The category describes source framing and archive coding; it is not a claim that the underlying supernatural account is true.`}
      path={narrativeTypePath(group.key)}
      parentHref="/narrative-types"
      parentLabel="Narrative types"
      records={group.records}
      notice="Classification follows the public archive coding layer and may be revised when source context or terminology is reviewed."
    />
  );
}
