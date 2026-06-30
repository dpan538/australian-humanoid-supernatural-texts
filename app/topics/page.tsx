import type { Metadata } from "next";
import Link from "next/link";
import { DisplayControls } from "@/components/display-controls";
import { SITE, absoluteUrl, siteConfig, socialImageMetadata } from "@/lib/site";
import { seoTopics, topicPath, topicUrl } from "@/lib/seo-topics";

const pageTitle = "Research Topics";
const brandedPageTitle = `${pageTitle} | ${SITE.name}`;
const pageDescription =
  "Search-oriented research topics for AusFigures, covering Australian supernatural public texts, Yowie records, bunyip references, ghosts, apparitions, spirit-person narratives, and source-grounded folklore.";

export const metadata: Metadata = {
  title: pageTitle,
  description: pageDescription,
  keywords: [...siteConfig.keywords, ...seoTopics.flatMap((topic) => topic.queryTerms)],
  alternates: {
    canonical: absoluteUrl("/topics"),
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: brandedPageTitle,
    description: pageDescription,
    url: absoluteUrl("/topics"),
    siteName: SITE.name,
    locale: siteConfig.locale,
    type: "website",
    images: [socialImageMetadata()],
  },
  twitter: {
    card: "summary_large_image",
    title: brandedPageTitle,
    description: pageDescription,
    images: [socialImageMetadata(SITE.twitterImagePath).url],
  },
};

export default function TopicsPage() {
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${absoluteUrl("/topics")}#webpage`,
        name: brandedPageTitle,
        url: absoluteUrl("/topics"),
        description: pageDescription,
        isPartOf: {
          "@id": `${siteConfig.siteUrl}/#website`,
        },
        mainEntity: {
          "@type": "ItemList",
          itemListElement: seoTopics.map((topic, index) => ({
            "@type": "ListItem",
            position: index + 1,
            name: topic.title,
            url: topicUrl(topic.slug),
          })),
        },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${absoluteUrl("/topics")}#breadcrumb`,
        itemListElement: [
          {
            "@type": "ListItem",
            position: 1,
            name: SITE.name,
            item: siteConfig.siteUrl,
          },
          {
            "@type": "ListItem",
            position: 2,
            name: "Research Topics",
            item: absoluteUrl("/topics"),
          },
        ],
      },
    ],
  };

  return (
    <main className="terminal-shell topic-shell">
      <div className="noise-layer" aria-hidden="true" />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
      <div className="terminal-stage">
        <section className="view-area view-area-about topic-view" aria-label="AusFigures research topics">
          <div className="about-view topic-page">
            <header className="topic-hero">
              <span className="tiny-label">RESEARCH TOPICS</span>
              <h1>AusFigures Topics</h1>
              <p>{pageDescription}</p>
            </header>

            <section className="about-command-strip topic-rule" aria-label="Archive interpretation rule">
              <i aria-hidden="true" />
              <span>SOURCE-GROUNDED PUBLIC-TEXT ARCHIVE</span>
              <b>PUBLIC SOURCE EXISTS != SUPERNATURAL CLAIM VERIFIED</b>
            </section>

            <section className="topic-index-panel topic-index-page-panel" aria-label="AusFigures search topics">
              <div className="about-module-head">
                <span>TOPIC INDEX</span>
                <i aria-hidden="true" />
              </div>
              <div className="topic-index-list">
                {seoTopics.map((topic) => (
                  <Link href={topicPath(topic.slug)} key={topic.slug}>
                    <span>{topic.title}</span>
                    <small>{topic.queryTerms.slice(0, 3).join(" / ")}</small>
                  </Link>
                ))}
              </div>
            </section>

            <nav className="about-actions topic-actions" aria-label="Archive views">
              <Link href="/">MAP</Link>
              <Link href="/source">SOURCE</Link>
              <Link href="/density">DENSITY</Link>
              <Link href="/about">ABOUT</Link>
            </nav>
          </div>
        </section>
        <div className="terminal-footer-controls">
          <DisplayControls />
        </div>
      </div>
    </main>
  );
}
