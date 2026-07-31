import type { Metadata } from "next";
import {
  SITE,
  absoluteUrl,
  siteConfig,
  socialCardImageMetadata,
  type SocialCardOptions,
} from "@/lib/site";

export function archivePageMetadata({
  title,
  description,
  path,
  index = true,
  keywords = [],
  social,
}: {
  title: string;
  description: string;
  path: string;
  index?: boolean;
  keywords?: string[];
  social?: Partial<Omit<SocialCardOptions, "title" | "description">>;
}): Metadata {
  const brandedTitle = title.includes(SITE.name) ? title : `${title} | ${SITE.name}`;
  const canonical = absoluteUrl(path);
  const socialImage = socialCardImageMetadata({
    title,
    description,
    eyebrow: social?.eyebrow ?? archiveEyebrow(path),
    metric: social?.metric,
    tone: social?.tone ?? archiveTone(path),
  });
  const pageKeywords = [...new Set([...siteConfig.keywords, ...keywords].filter(Boolean))].slice(0, 16);

  return {
    title,
    description,
    keywords: pageKeywords,
    category: "research",
    alternates: {
      canonical,
      types: {
        "application/rss+xml": absoluteUrl("/feed.xml"),
      },
    },
    robots: {
      index,
      follow: true,
    },
    referrer: "origin-when-cross-origin",
    openGraph: {
      title: brandedTitle,
      description,
      url: canonical,
      siteName: SITE.name,
      locale: siteConfig.locale,
      type: "website",
      images: [socialImage],
    },
    twitter: {
      card: "summary_large_image",
      title: brandedTitle,
      description,
      images: [socialImage],
    },
  };
}

function archiveEyebrow(path: string) {
  if (path.startsWith("/records/")) return "PUBLIC-TEXT RECORD";
  if (path.startsWith("/figures/")) return "FIGURE ENCYCLOPEDIA";
  if (path.startsWith("/sources/")) return "PUBLIC SOURCE";
  if (path.startsWith("/places/")) return "NARRATIVE GEOGRAPHY";
  if (path.startsWith("/periods/")) return "SOURCE PERIOD";
  if (path.startsWith("/narrative-types/")) return "NARRATIVE TYPE";
  return "AUSFIGURES RESEARCH INDEX";
}

function archiveTone(path: string): SocialCardOptions["tone"] {
  if (path.startsWith("/records")) return "paper";
  if (path.startsWith("/figures")) return "blue";
  if (path.startsWith("/sources")) return "sage";
  if (path.startsWith("/places")) return "clay";
  if (path.startsWith("/periods")) return "ochre";
  if (path.startsWith("/narrative-types")) return "ink";
  return "paper";
}

export function archiveBreadcrumbJsonLd(items: Array<{ name: string; path: string }>) {
  return {
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}
