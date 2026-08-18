import Link from "next/link";
import {
  ArchiveIndexStructuredData,
  ArchivePublicationPage,
  PublicationSection,
} from "@/components/archive-publication";
import { archiveInventory, loadArchiveData } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { SITE } from "@/lib/site";

export const metadata = archivePageMetadata({
  title: "AusFigures Data, Coverage, and Index Policy",
  description:
    "Public data scope, page inventory, search-index eligibility, provenance boundaries, and machine-readable access for AusFigures.",
  path: "/data",
  keywords: ["AusFigures dataset", "Australian supernatural public-text data", "archive coverage methodology"],
});

export default async function DataPage() {
  const data = await loadArchiveData();
  const inventory = archiveInventory(data);
  return (
    <ArchivePublicationPage
      eyebrow="DATA & COVERAGE"
      title="Public archive data"
      intro="This page separates public record totals from search-index eligibility and from non-record research layers. The distinction prevents metadata-only items, leads, and overlays from being promoted into accepted public records."
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/data", label: "Data" },
      ]}
      stats={[
        { label: "Accepted public records", value: inventory.publicDataRecords },
        { label: "Record pages", value: inventory.recordPages },
        { label: "Public reviewed records", value: inventory.indexableRecordPages },
        { label: "Review-only record pages", value: inventory.reviewOnlyRecordPages },
      ]}
      notice="Search indexing is intentionally limited to the main research tools and selected figure pages. Record details remain available as supporting archive evidence without entering the sitemap."
    >
      <ArchiveIndexStructuredData
        path="/data"
        title="AusFigures Data, Coverage, and Index Policy"
        description="Public data scope, page inventory, search-index eligibility, provenance boundaries, and machine-readable access for AusFigures."
        schemaType="DataCatalog"
        items={[
          { href: "/figures", title: "Supernatural humanoid dictionary" },
          { href: "/dashboard", title: "Research dashboard" },
          { href: "/density", title: "Density explorer" },
          { href: "/source", title: "Source register" },
        ]}
      />
      <PublicationSection title="Generated page inventory">
        <dl className="publication-definition-list">
          <div><dt>Paginated record indexes</dt><dd>{inventory.recordIndexPages}</dd></div>
          <div><dt>Narrative-type pages</dt><dd>{inventory.narrativeTypePages}</dd></div>
          <div><dt>Recurring label pages</dt><dd>{inventory.labelPages}</dd></div>
          <div><dt>Encyclopedia figure pages</dt><dd>{inventory.figurePages}</dd></div>
          <div><dt>Public figure pages</dt><dd>{inventory.indexableFigurePages}</dd></div>
          <div><dt>Review-only figure pages</dt><dd>{inventory.reviewOnlyFigurePages}</dd></div>
          <div><dt>Source pages</dt><dd>{inventory.sourcePages}</dd></div>
          <div><dt>State and territory pages</dt><dd>{inventory.placePages}</dd></div>
          <div><dt>Period pages</dt><dd>{inventory.periodPages}</dd></div>
        </dl>
      </PublicationSection>
      <PublicationSection title="Machine-readable access">
        <p>
          The current public export is available as JSON. It contains accepted public record display data and remains
          separate from metadata-only gap items, leads, source intelligence, and research overlays.
        </p>
        <div className="publication-link-row">
          <a href="/data/frontend-data.json">Public frontend JSON</a>
          <Link href="/records">Human-readable record index</Link>
          <Link href="/figures">Supernatural humanoid encyclopedia</Link>
          <Link href="/cite">Citation guidance</Link>
          <a href="/feed.xml">Recent-record RSS feed</a>
        </div>
      </PublicationSection>
      <PublicationSection title="Interpretation limits">
        <ul className="publication-prose-list">
          <li>Record counts measure collected public texts, not supernatural prevalence.</li>
          <li>Map points identify display locations, not habitats, populations, or proof.</li>
          <li>Source publication does not imply source endorsement of AusFigures.</li>
          <li>Restricted or private cultural knowledge remains outside the public archive scope.</li>
        </ul>
      </PublicationSection>
    </ArchivePublicationPage>
  );
}
