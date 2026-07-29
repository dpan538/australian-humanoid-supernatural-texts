import {
  ArchiveCollectionGrid,
  ArchiveIndexStructuredData,
  ArchivePublicationPage,
  PublicationSection,
} from "@/components/archive-publication";
import { loadArchiveData, placeGroups } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { placePath } from "@/lib/archive-routing";
import { SITE } from "@/lib/site";

export const metadata = archivePageMetadata({
  title: "Australian Places in Supernatural Humanoid Public Texts",
  description:
    "Browse source-grounded supernatural humanoid public-text records by Australian state and territory.",
  path: "/places",
  keywords: ["Australian supernatural places", "Australian folklore by state", "public-text narrative geography"],
});

export default async function PlacesPage() {
  const data = await loadArchiveData();
  const groups = placeGroups(data);
  return (
    <ArchivePublicationPage
      eyebrow="PLACE INDEX"
      title="States and territories"
      intro="Place pages organise the geography described or associated with public-text records. A location may be a narrative setting, reported place, publication context, or broad association; it is never presented as proof, habitat, or population distribution."
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/places", label: "Places" },
      ]}
      stats={[
        { label: "States / territories", value: groups.length },
        { label: "Search-ready located records", value: groups.reduce((sum, group) => sum + group.records.length, 0) },
        { label: "Geographic scope", value: "Australia" },
      ]}
    >
      <ArchiveIndexStructuredData
        path="/places"
        title="Australian Places in Supernatural Humanoid Public Texts"
        description="Browse source-grounded supernatural humanoid public-text records by Australian state and territory."
        items={groups.map((group) => ({ href: placePath(group.key), title: group.label }))}
      />
      <PublicationSection title="Browse narrative geography">
        <ArchiveCollectionGrid
          items={groups.map((group) => ({
            href: placePath(group.key),
            title: group.label,
            count: group.records.length,
            description: "Public-text place association; not supernatural distribution.",
          }))}
        />
      </PublicationSection>
    </ArchivePublicationPage>
  );
}
