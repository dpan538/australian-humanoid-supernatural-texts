import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArchiveRecordCollectionPage } from "@/components/archive-publication";
import { loadArchiveData, placeGroups } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { archiveSlug, placePath } from "@/lib/archive-routing";

type PlacePageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  return placeGroups(data).map((group) => ({ slug: archiveSlug(group.key) }));
}

export async function generateMetadata({ params }: PlacePageProps): Promise<Metadata> {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = placeGroups(data).find((item) => archiveSlug(item.key) === slug);
  if (!group) {
    return {};
  }
  return archivePageMetadata({
    title: `${group.label} Supernatural Humanoid Public-Text Records`,
    description: `Browse ${group.records.length} source-grounded AusFigures public-text records associated with ${group.label}.`,
    path: placePath(group.key),
    index: false,
    keywords: [`${group.label} supernatural folklore`, `${group.label} ghost and humanoid records`],
    social: {
      eyebrow: "NARRATIVE GEOGRAPHY",
      metric: `${group.records.length.toLocaleString("en-AU")} records`,
      tone: "clay",
    },
  });
}

export default async function PlaceDetailPage({ params }: PlacePageProps) {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = placeGroups(data).find((item) => archiveSlug(item.key) === slug);
  if (!group) {
    notFound();
  }
  return (
    <ArchiveRecordCollectionPage
      eyebrow="NARRATIVE GEOGRAPHY"
      title={group.label}
      intro={`These public-text records carry a reviewed ${group.label} association. Locations describe narrative or source geography and must not be interpreted as verified supernatural distribution, habitat, frequency, or tourism guidance.`}
      path={placePath(group.key)}
      parentHref="/places"
      parentLabel="Places"
      records={group.records}
      notice="Map and place labels identify public-record context, not proof of an event or being."
    />
  );
}
