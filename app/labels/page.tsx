import {
  ArchiveCollectionGrid,
  ArchivePublicationPage,
  PublicationSection,
} from "@/components/archive-publication";
import { labelGroups, loadArchiveData } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { labelPath } from "@/lib/archive-routing";
import { SITE } from "@/lib/site";

export const metadata = archivePageMetadata({
  title: "Figure and Public-Text Labels",
  description:
    "Browse recurring figure and descriptive labels recorded in the AusFigures Australian supernatural humanoid public-text archive.",
  path: "/labels",
  keywords: ["Australian folklore figure labels", "supernatural humanoid labels", "ghost and spirit public texts"],
});

export default async function LabelsPage() {
  const data = await loadArchiveData();
  const groups = labelGroups(data);
  return (
    <ArchivePublicationPage
      eyebrow="PUBLIC-TEXT VOCABULARY"
      title="Figure and descriptive labels"
      intro="This vocabulary records recurring labels as printed or coded in public sources. It includes broad terms, named figures, apparition labels, spirit-person wording, giants, witches, devils, hairy humanoids, and other humanoid or humanoid-adjacent descriptions."
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/labels", label: "Labels" },
      ]}
      stats={[
        { label: "Published label pages", value: groups.length },
        { label: "Minimum records per page", value: 4 },
        { label: "Classification", value: "Source vocabulary" },
      ]}
      notice="A label page is not an assertion that different traditions, beings, names, or source usages are equivalent. Historical and culturally specific terminology remains tied to its cited source context."
    >
      <PublicationSection title="Browse recurring labels">
        <ArchiveCollectionGrid
          items={groups.map((group) => ({
            href: labelPath(group.key),
            title: group.label,
            count: group.records.length,
            description: "Recurring public-text label; not an entity or identity claim.",
          }))}
        />
      </PublicationSection>
    </ArchivePublicationPage>
  );
}
