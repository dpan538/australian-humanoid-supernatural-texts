import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DisplayControls } from "@/components/display-controls";
import { SITE, absoluteUrl, siteConfig, socialImageMetadata } from "@/lib/site";
import { seoTopics, topicBySlug, topicPath, topicUrl } from "@/lib/seo-topics";

type TopicPageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return seoTopics.map((topic) => ({ slug: topic.slug }));
}

export async function generateMetadata({ params }: TopicPageProps): Promise<Metadata> {
  const { slug } = await params;
  const topic = topicBySlug(slug);

  if (!topic) {
    return {};
  }

  const canonical = topicUrl(topic.slug);
  const title = topic.title;
  const brandedTitle = `${topic.title} | ${SITE.name}`;

  return {
    title,
    description: topic.description,
    keywords: [...siteConfig.keywords, ...topic.queryTerms],
    category: "research",
    alternates: {
      canonical,
    },
    robots: {
      index: true,
      follow: true,
    },
    openGraph: {
      title: brandedTitle,
      description: topic.description,
      url: canonical,
      siteName: SITE.name,
      locale: siteConfig.locale,
      type: "website",
      images: [socialImageMetadata()],
    },
    twitter: {
      card: "summary_large_image",
      title: brandedTitle,
      description: topic.description,
      images: [socialImageMetadata(SITE.twitterImagePath).url],
    },
  };
}

export default async function TopicPage({ params }: TopicPageProps) {
  const { slug } = await params;
  const topic = topicBySlug(slug);

  if (!topic) {
    notFound();
  }

  const brandedTitle = `${topic.title} | ${SITE.name}`;

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${topicUrl(topic.slug)}#webpage`,
        name: brandedTitle,
        url: topicUrl(topic.slug),
        description: topic.description,
        isPartOf: {
          "@id": `${siteConfig.siteUrl}/#website`,
        },
        about: topic.queryTerms,
        mainEntity: {
          "@id": `${siteConfig.siteUrl}/#dataset`,
        },
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${topicUrl(topic.slug)}#breadcrumb`,
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
            name: "Research topics",
            item: absoluteUrl("/topics"),
          },
          {
            "@type": "ListItem",
            position: 3,
            name: topic.title,
            item: topicUrl(topic.slug),
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
        <section className="view-area view-area-about topic-view" aria-label={`${topic.title} research topic`}>
          <div className="about-view topic-page">
            <header className="topic-hero">
              <span className="tiny-label">{topic.eyebrow}</span>
              <h1>{topic.title}</h1>
              <p>{topic.description}</p>
            </header>

            <section className="about-command-strip topic-rule" aria-label="Archive interpretation rule">
              <i aria-hidden="true" />
              <span>SOURCE-GROUNDED PUBLIC-TEXT ARCHIVE</span>
              <b>PUBLIC SOURCE EXISTS != SUPERNATURAL CLAIM VERIFIED</b>
            </section>

            <section className="about-grid topic-grid" aria-label={`${topic.title} topic notes`}>
              <TopicModule kicker="TOPIC SUMMARY" title="Search language, research framing">
                {topic.summary}
              </TopicModule>
              <TopicModule kicker="ARCHIVE SCOPE" title="What may appear here">
                {topic.scope}
              </TopicModule>
              <TopicModule kicker="INTERPRETATION LIMIT" title="How to read records">
                {topic.interpretation}
              </TopicModule>
              <details className="about-module about-accordion-module topic-module" open>
                <summary className="about-module-head">
                  <span>SEARCH TERMS</span>
                  <i aria-hidden="true" />
                </summary>
                <h2>Related discovery language</h2>
                <div className="topic-term-list">
                  {topic.queryTerms.map((term) => (
                    <span key={term}>{term}</span>
                  ))}
                </div>
              </details>
            </section>

            <nav className="about-actions topic-actions" aria-label="Archive views">
              <Link href="/">MAP</Link>
              <Link href="/source">SOURCE</Link>
              <Link href="/density">DENSITY</Link>
              <Link href="/about">ABOUT</Link>
            </nav>

            <section className="topic-index-panel" aria-label="Other AusFigures research topics">
              <div className="about-module-head">
                <span>RELATED TOPICS</span>
                <i aria-hidden="true" />
              </div>
              <div className="topic-index-list">
                {seoTopics
                  .filter((item) => item.slug !== topic.slug)
                  .map((item) => (
                    <Link href={topicPath(item.slug)} key={item.slug}>
                      <span>{item.title}</span>
                      <small>{item.queryTerms.slice(0, 2).join(" / ")}</small>
                    </Link>
                  ))}
              </div>
            </section>
          </div>
        </section>
        <div className="terminal-footer-controls">
          <DisplayControls />
        </div>
      </div>
    </main>
  );
}

function TopicModule({ kicker, title, children }: { kicker: string; title: string; children: string }) {
  return (
    <details className="about-module about-accordion-module topic-module" open>
      <summary className="about-module-head">
        <span>{kicker}</span>
        <i aria-hidden="true" />
      </summary>
      <h2>{title}</h2>
      <p>{children}</p>
    </details>
  );
}
