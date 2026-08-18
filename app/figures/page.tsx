import { FigureEncyclopedia } from "@/components/figures/figure-encyclopedia";
import { loadArchiveData } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { buildFigureDictionaryEntries } from "@/lib/figure-dictionary";
import { isIndexedFigureSlug } from "@/lib/search-index-policy";
import { SITE, absoluteUrl, siteConfig } from "@/lib/site";

export const metadata = archivePageMetadata({
  title: "Australian Supernatural Humanoid Encyclopedia",
  description:
    "Search every search-ready and review-stage supernatural humanoid figure category represented by AusFigures, including rare public-text labels, aliases, records, places, periods, and related classifications.",
  path: "/figures",
  keywords: [
    "Australian supernatural humanoid encyclopedia",
    "Australian folklore dictionary",
    "Australian folklore beings",
    "Australian hairy humanoids",
    "Australian ghosts spirits giants fairies",
    "rare Australian supernatural figures",
  ],
});

export default async function FiguresPage() {
  const data = await loadArchiveData();
  const entries = buildFigureDictionaryEntries(data);
  const indexed = entries.filter(
    (entry) => entry.indexEligible && isIndexedFigureSlug(entry.slug),
  );
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${absoluteUrl("/figures")}#webpage`,
        name: `Australian Supernatural Humanoid Encyclopedia | ${SITE.name}`,
        url: absoluteUrl("/figures"),
        description:
          "A searchable archive dictionary connecting recurring and rare supernatural humanoid figure categories to public records, source labels, narrative types, places, and periods.",
        inLanguage: "en-AU",
        dateModified: siteConfig.contentUpdatedDate,
        isPartOf: { "@id": `${siteConfig.siteUrl}/#website` },
        publisher: { "@id": `${siteConfig.siteUrl}/#organization` },
        mainEntity: { "@id": `${absoluteUrl("/figures")}#term-set` },
      },
      {
        "@type": "DefinedTermSet",
        "@id": `${absoluteUrl("/figures")}#term-set`,
        name: "AusFigures supernatural humanoid figure categories",
        url: absoluteUrl("/figures"),
        inLanguage: "en-AU",
        hasDefinedTerm: indexed.map((entry) => ({
          "@type": "DefinedTerm",
          name: entry.label,
          url: absoluteUrl(`/figures/${entry.slug}`),
          description: entry.description,
          alternateName: entry.aliases,
        })),
      },
    ],
  };

  return (
    <>
      <script
        id="figure-encyclopedia-structured-data"
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }}
      />
      <FigureEncyclopedia entries={entries} />
    </>
  );
}
