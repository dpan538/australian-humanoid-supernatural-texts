import Link from "next/link";
import {
  ArchiveIndexStructuredData,
  ArchivePublicationPage,
  PublicationSection,
} from "@/components/archive-publication";
import { CitationSamples } from "@/components/citation-samples";
import { archiveInventory, loadArchiveData } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { buildProjectCitations } from "@/lib/citations";
import { SITE, siteConfig } from "@/lib/site";

export const metadata = archivePageMetadata({
  title: "Cite AusFigures",
  description:
    "Citation, attribution, version, scope, and reuse guidance for the AusFigures Australian supernatural humanoid public-text archive.",
  path: "/cite",
  keywords: ["cite AusFigures", "Australian supernatural dataset citation", "digital humanities archive citation"],
});

export default async function CitePage() {
  const data = await loadArchiveData();
  const inventory = archiveInventory(data);
  const generatedDate = data.generated_at.slice(0, 10);
  const citationSamples = buildProjectCitations(generatedDate);

  return (
    <ArchivePublicationPage
      eyebrow="CITATION & ATTRIBUTION"
      title="Cite AusFigures"
      intro="AusFigures is a source-grounded digital archive. Cite the project for its aggregation and coding, and cite each original public source when discussing an individual record."
      breadcrumbs={[
        { href: "/", label: SITE.name },
        { href: "/cite", label: "Cite" },
      ]}
      stats={[
        { label: "Public record pages", value: inventory.recordPages },
        { label: "Search-ready records", value: inventory.indexableRecordPages },
        { label: "Data generated", value: generatedDate },
        { label: "Maintainer", value: siteConfig.creator },
      ]}
      notice="AusFigures records the existence and context of public texts. It does not verify supernatural claims and is not an official repository of restricted cultural knowledge."
    >
      <ArchiveIndexStructuredData
        path="/cite"
        title="Cite AusFigures"
        description="Citation, attribution, version, scope, and reuse guidance for the AusFigures Australian supernatural humanoid public-text archive."
        schemaType="TechArticle"
      />
      <PublicationSection title="Copy a project citation">
        <p>
          Choose the format required by your institution. These samples identify the live public export date without
          claiming a DOI or peer-reviewed edition.
        </p>
        <CitationSamples samples={citationSamples} compact />
      </PublicationSection>
      <PublicationSection title="Record-level citation">
        <p>
          Use the permanent AusFigures record URL for the archive context, then cite the original source URL, publication,
          author, and source date shown on that record page. Public-source terminology should not be detached from its
          historical or cultural context.
        </p>
      </PublicationSection>
      <PublicationSection title="Version and reuse">
        <ul className="publication-prose-list">
          <li>The current machine-readable public export reports schema <code>{data.schema_version}</code>.</li>
          <li>Public records, research leads, metadata-only gap items, and map overlays remain separate layers.</li>
          <li>Original-source rights and access conditions continue to apply.</li>
          <li>A DOI has not been asserted on this page; a future deposited release should add its persistent identifier here.</li>
        </ul>
        <div className="publication-link-row">
          <Link href="/data">Data and coverage</Link>
          <a href={SITE.repositoryUrl} rel="noopener noreferrer" target="_blank">Project repository</a>
        </div>
      </PublicationSection>
    </ArchivePublicationPage>
  );
}
