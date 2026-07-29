import {
  ArchiveCollectionGrid,
  ArchiveIndexStructuredData,
  ArchivePublicationPage,
  PublicationSection,
} from "@/components/archive-publication";
import { loadArchiveData, periodGroups } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { periodPath } from "@/lib/archive-routing";
import { SITE } from "@/lib/site";

export const metadata = archivePageMetadata({
  title: "Periods in Australian Supernatural Humanoid Public Texts",
  description:
    "Browse the AusFigures source-grounded public-text archive by historical period from 1825 to the present, including undated public records.",
  path: "/periods",
  keywords: ["Australian supernatural history", "historical ghost records Australia", "supernatural humanoid public texts by period"],
});

export default async function PeriodsPage() {
  const data = await loadArchiveData();
  const groups = periodGroups(data);
  return (
    <ArchivePublicationPage
      eyebrow="TIME INDEX"
      title="Historical periods"
      intro="Period pages organise records by publication or source date. They show changes in the surviving and collected public-text corpus, not changes in the real-world frequency of supernatural events."
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/periods", label: "Periods" },
      ]}
      stats={[
        { label: "Published periods", value: groups.length },
        { label: "Dated and undated records", value: groups.reduce((sum, group) => sum + group.records.length, 0) },
        { label: "Archive span", value: "1825–2026" },
      ]}
    >
      <ArchiveIndexStructuredData
        path="/periods"
        title="Periods in Australian Supernatural Humanoid Public Texts"
        description="Browse the AusFigures source-grounded public-text archive by historical period from 1825 to the present, including undated public records."
        items={groups.map((group) => ({ href: periodPath(group.key), title: group.label }))}
      />
      <PublicationSection title="Browse by source period">
        <ArchiveCollectionGrid
          items={groups.map((group) => ({
            href: periodPath(group.key),
            title: group.label,
            count: group.records.length,
            description: group.period.context || "Public-text records grouped by source date.",
          }))}
        />
      </PublicationSection>
    </ArchivePublicationPage>
  );
}
