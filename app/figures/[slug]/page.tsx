import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FigureEncyclopedia } from "@/components/figures/figure-encyclopedia";
import {
  encyclopediaFigureBySlug,
  encyclopediaFigureGroups,
  loadArchiveData,
} from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { figurePath } from "@/lib/archive-routing";
import { buildFigureDictionaryEntries } from "@/lib/figure-dictionary";
import { SITE, absoluteUrl, siteConfig } from "@/lib/site";

type FigurePageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  return encyclopediaFigureGroups(data).map((group) => ({ slug: group.slug }));
}

export async function generateMetadata({ params }: FigurePageProps): Promise<Metadata> {
  const { slug } = await params;
  const data = await loadArchiveData();
  const group = encyclopediaFigureBySlug(data, slug);
  if (!group) {
    return {};
  }
  return archivePageMetadata({
    title: `${group.label} — Australian Supernatural Humanoid Encyclopedia`,
    description: compactDescription(
      `${group.label} in the AusFigures supernatural humanoid dictionary. Search aliases and browse ${group.records.length} connected public records, sources, narrative types, places, periods, and related figures.`,
    ),
    path: figurePath(group.slug),
    index: group.indexEligible,
    keywords: [
      group.label,
      `${group.label} Australia`,
      `${group.label} folklore`,
      `${group.label} public records`,
      ...group.aliases,
      ...group.taxonomyFigures.flatMap((figure) => [
        figure.cluster,
        figure.humanoid_degree ?? "",
        figure.ontology_default ?? "",
      ]),
    ].filter(Boolean),
  });
}

export default async function FigurePage({ params }: FigurePageProps) {
  const { slug } = await params;
  const data = await loadArchiveData();
  const entries = buildFigureDictionaryEntries(data);
  const entry = entries.find((item) => item.slug === slug);
  if (!entry) {
    notFound();
  }

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${absoluteUrl(figurePath(entry.slug))}#webpage`,
        name: `${entry.label} — Australian Supernatural Humanoid Encyclopedia`,
        url: absoluteUrl(figurePath(entry.slug)),
        description: entry.description,
        inLanguage: "en-AU",
        dateModified: siteConfig.contentUpdatedDate,
        isPartOf: { "@id": `${siteConfig.siteUrl}/#website` },
        publisher: { "@id": `${siteConfig.siteUrl}/#organization` },
        mainEntity: { "@id": `${absoluteUrl(figurePath(entry.slug))}#term` },
        hasPart: entry.records.map((record) => ({
          "@type": "WebPage",
          name: record.title,
          url: absoluteUrl(record.href),
        })),
      },
      {
        "@type": "DefinedTerm",
        "@id": `${absoluteUrl(figurePath(entry.slug))}#term`,
        name: entry.label,
        alternateName: entry.aliases,
        description: entry.description,
        url: absoluteUrl(figurePath(entry.slug)),
        inDefinedTermSet: { "@id": `${absoluteUrl("/figures")}#term-set` },
        subjectOf: {
          "@type": "ItemList",
          numberOfItems: entry.recordCount,
          itemListElement: entry.records.map((record, index) => ({
            "@type": "ListItem",
            position: index + 1,
            name: record.title,
            url: absoluteUrl(record.href),
          })),
        },
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: SITE.name, item: siteConfig.siteUrl },
          { "@type": "ListItem", position: 2, name: "Figures", item: absoluteUrl("/figures") },
          {
            "@type": "ListItem",
            position: 3,
            name: entry.label,
            item: absoluteUrl(figurePath(entry.slug)),
          },
        ],
      },
    ],
  };

  return (
    <>
      <script
        id={`figure-${entry.slug}-structured-data`}
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }}
      />
      <FigureEncyclopedia entries={entries} initialSlug={entry.slug} />
    </>
  );
}

function compactDescription(value: string, limit = 158) {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trimEnd()}…` : text;
}
