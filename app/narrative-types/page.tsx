import {
  ArchiveCollectionGrid,
  ArchiveIndexStructuredData,
  ArchivePublicationPage,
  PublicationSection,
} from "@/components/archive-publication";
import { loadArchiveData, narrativeTypeGroups } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { narrativeTypePath } from "@/lib/archive-routing";
import { SITE } from "@/lib/site";

export const metadata = archivePageMetadata({
  title: "Supernatural Humanoid Narrative Types",
  description:
    "Browse the AusFigures public-text archive by narrative type, including hairy humanoid accounts, apparitions, spirit-person narratives, giants, legends, encounters, belief records, and retellings.",
  path: "/narrative-types",
  keywords: ["supernatural humanoid narrative types", "Australian apparition accounts", "spirit-person narratives"],
});

export default async function NarrativeTypesPage() {
  const data = await loadArchiveData();
  const groups = narrativeTypeGroups(data);
  return (
    <ArchivePublicationPage
      eyebrow="CLASSIFICATION INDEX"
      title="Narrative types"
      intro="This index organises public texts by the form of narrative recorded in the source. It is broader than any single figure label and keeps encounters, apparitions, spirit-person narratives, giants, legends, belief descriptions, and retellings analytically distinct."
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/narrative-types", label: "Narrative types" },
      ]}
      stats={[
        { label: "Narrative types", value: groups.length },
        { label: "Search-ready records", value: groups.reduce((sum, group) => sum + group.records.length, 0) },
        { label: "Archive scope", value: "Australia" },
      ]}
      notice="Narrative type describes how a public source frames material. It does not verify the event, being, belief, or interpretation described."
    >
      <ArchiveIndexStructuredData
        path="/narrative-types"
        title="Supernatural Humanoid Narrative Types"
        description="Browse the AusFigures public-text archive by narrative type, including hairy humanoid accounts, apparitions, spirit-person narratives, giants, legends, encounters, belief records, and retellings."
        items={groups.map((group) => ({ href: narrativeTypePath(group.key), title: group.label }))}
      />
      <PublicationSection title="Browse by narrative form">
        <ArchiveCollectionGrid
          items={groups.map((group) => ({
            href: narrativeTypePath(group.key),
            title: group.label,
            count: group.records.length,
            description: `Source-grounded ${group.label.toLowerCase()} in the public archive.`,
          }))}
        />
      </PublicationSection>
    </ArchivePublicationPage>
  );
}
