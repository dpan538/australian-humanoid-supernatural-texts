import type { Metadata } from "next";

export const SITE = {
  name: "AusFigures",
  fullTitle: "Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters",
  domain: "ausfigures.com",
  url: "https://ausfigures.com",
  canonicalOrigin: "https://ausfigures.com",
  repositoryUrl: "https://github.com/dpan538/australian-humanoid-supernatural-texts",
  primaryRoute: "/",
  routes: ["/", "/dashboard", "/density", "/source", "/about"],
  socialImagePath: "/opengraph-image",
  twitterImagePath: "/twitter-image",
  socialImageAlt: "AusFigures map social preview",
  description:
    "A source-grounded public-text research archive for Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings.",
} as const;

export const siteConfig = {
  ...SITE,
  siteUrl: SITE.url,
  siteName: SITE.name,
  shortDescription: SITE.description,
  creator: "Dai Pan",
  locale: "en_AU",
  releaseDate: "2026-06-29",
  keywords: [
    "AusFigures",
    "Australian public text archive",
    "supernatural humanoid narratives",
    "source-grounded archive",
    "digital humanities",
    "Australian folklore research",
    "public record map",
    "mapped public records",
    "public source register",
  ],
  routeMetadata: [
    {
      path: "/",
      title: "AusFigures Map",
      description:
        "Source-grounded map view for Australian supernatural humanoid narratives in public texts. Map markers are display locations for records, not proof, habitats, or populations.",
      priority: 1.0,
      changeFrequency: "monthly",
    },
    {
      path: "/map",
      canonicalPath: "/",
      title: "Map",
      description:
        "Map view for verified display locations in the AusFigures public-text archive. Markers identify records, not supernatural proof or habitats.",
      priority: 0.0,
      changeFrequency: "monthly",
    },
    {
      path: "/dashboard",
      title: "Research Dashboard",
      description:
        "Overview of the AusFigures public-text corpus by period, source family, narrative type, figure label, and mapped-record coverage.",
      priority: 0.8,
      changeFrequency: "monthly",
    },
    {
      path: "/density",
      title: "Density Explorer",
      description:
        "Source, query, and figure-density views for comparing public-text signals across the AusFigures research archive.",
      priority: 0.7,
      changeFrequency: "monthly",
    },
    {
      path: "/source",
      title: "Source Register",
      description:
        "Source register and source-family rollups for the AusFigures public-text archive.",
      priority: 0.8,
      changeFrequency: "monthly",
    },
    {
      path: "/about",
      title: "About AusFigures",
      description:
        "Scope, methods, source policy, mapping limits, and ethical interpretation rules for AusFigures.",
      priority: 0.8,
      changeFrequency: "monthly",
    },
  ],
} as const;

export type SiteRoutePath = (typeof siteConfig.routeMetadata)[number]["path"];

export function absoluteUrl(path = "/") {
  return new URL(path, SITE.canonicalOrigin).toString();
}

export function socialImageMetadata(path: string = SITE.socialImagePath) {
  return {
    url: absoluteUrl(path),
    width: 1200,
    height: 630,
    alt: SITE.socialImageAlt,
  };
}

function brandedTitle(title: string) {
  return title.includes(siteConfig.siteName) ? title : `${title} | ${siteConfig.siteName}`;
}

export function routeConfig(path: SiteRoutePath) {
  return siteConfig.routeMetadata.find((route) => route.path === path) ?? siteConfig.routeMetadata[0];
}

export function metadataForRoute(path: SiteRoutePath): Metadata {
  const route = routeConfig(path);
  const title = route.title;
  const description = route.description;
  const metaTitle = brandedTitle(title);
  const canonicalPath = "canonicalPath" in route ? route.canonicalPath : route.path;

  return {
    title,
    description,
    keywords: [...siteConfig.keywords],
    category: "research",
    alternates: {
      canonical: absoluteUrl(canonicalPath),
    },
    robots: {
      index: true,
      follow: true,
    },
    openGraph: {
      title: metaTitle,
      description,
      url: absoluteUrl(canonicalPath),
      siteName: siteConfig.siteName,
      locale: siteConfig.locale,
      type: "website",
      images: [socialImageMetadata()],
    },
    twitter: {
      card: "summary_large_image",
      title: metaTitle,
      description,
      images: [socialImageMetadata(SITE.twitterImagePath).url],
    },
  };
}
