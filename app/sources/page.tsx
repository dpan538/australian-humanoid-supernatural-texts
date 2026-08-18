import {
  ArchiveCollectionGrid,
  ArchiveIndexStructuredData,
  ArchivePublicationPage,
  PublicationSection,
} from "@/components/archive-publication";
import { loadArchiveData, sourceGroups } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { humanizeArchiveCode, sourcePath } from "@/lib/archive-routing";
import { SITE } from "@/lib/site";

export const metadata = archivePageMetadata({
  title: "Public Source Organisations and Collections",
  description:
    "Browse public source organisations, repositories, institutional pages, books, archives, and metadata collections represented in the AusFigures public-text archive.",
  path: "/sources",
  index: false,
  keywords: ["Australian supernatural sources", "public archive source register", "digital humanities sources"],
});

export default async function SourcesPage() {
  const data = await loadArchiveData();
  const groups = sourceGroups(data);
  return (
    <ArchivePublicationPage
      eyebrow="SOURCE INDEX"
      title="Public sources"
      intro="AusFigures is organised around public source context. This index connects records to repositories, public-domain books, institutional pages, media collections, catalogues, and public web archives without treating source publication as verification of a supernatural claim."
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/sources", label: "Sources" },
      ]}
      stats={[
        { label: "Sources with search-ready records", value: groups.length },
        { label: "Search-ready records", value: groups.reduce((sum, group) => sum + group.records.length, 0) },
        { label: "Interactive register", value: "Available" },
      ]}
      notice="Source pages describe provenance and public access. They do not imply endorsement by the source organisation."
    >
      <ArchiveIndexStructuredData
        path="/sources"
        title="Public Source Organisations and Collections"
        description="Browse public source organisations, repositories, institutional pages, books, archives, and metadata collections represented in the AusFigures public-text archive."
        items={groups.map((group) => ({
          href: sourcePath(group.sourceId, group.label),
          title: group.label,
        }))}
      />
      <PublicationSection title="Browse source collections">
        <ArchiveCollectionGrid
          items={groups.map((group) => ({
            href: sourcePath(group.sourceId, group.label),
            title: group.label,
            count: group.records.length,
            description: humanizeArchiveCode(group.source?.source_type || group.records[0]?.source_type),
          }))}
        />
      </PublicationSection>
    </ArchivePublicationPage>
  );
}
