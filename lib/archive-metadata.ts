import type { Metadata } from "next";
import { SITE, absoluteUrl, siteConfig, socialImageMetadata } from "@/lib/site";

export function archivePageMetadata({
  title,
  description,
  path,
  index = true,
  keywords = [],
}: {
  title: string;
  description: string;
  path: string;
  index?: boolean;
  keywords?: string[];
}): Metadata {
  const brandedTitle = title.includes(SITE.name) ? title : `${title} | ${SITE.name}`;
  const canonical = absoluteUrl(path);

  return {
    title,
    description,
    keywords: [...siteConfig.keywords, ...keywords],
    category: "research",
    alternates: {
      canonical,
    },
    robots: {
      index,
      follow: true,
    },
    openGraph: {
      title: brandedTitle,
      description,
      url: canonical,
      siteName: SITE.name,
      locale: siteConfig.locale,
      type: "website",
      images: [socialImageMetadata()],
    },
    twitter: {
      card: "summary_large_image",
      title: brandedTitle,
      description,
      images: [socialImageMetadata(SITE.twitterImagePath).url],
    },
  };
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
