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
  iconPath: "/icon.svg",
  faviconPath: "/favicon.ico",
  pngIconPath: "/icon-192.png",
  logoPath: "/icon-512.png",
  appleIconPath: "/apple-icon.png",
  socialImageAlt: "AusFigures source-grounded Australian supernatural public-text archive preview",
  description:
    "Source-grounded public-text archive of Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings.",
} as const;

export const siteConfig = {
  ...SITE,
  siteUrl: SITE.url,
  siteName: SITE.name,
  shortDescription: SITE.description,
  creator: "Dai Pan",
  locale: "en_AU",
  releaseDate: "2026-06-30",
  searchTopics: [
    "Australian supernatural",
    "Australian supernatural folklore",
    "Australian supernatural humanoids",
    "Australian folklore archive",
    "Yowie records",
    "bunyip public texts",
    "Australian apparition records",
    "Australian ghost records",
    "spirit-person narratives",
    "Australian legends and encounters",
    "humanoid supernatural encounters",
    "source-grounded public records",
  ],
  keywords: [
    "AusFigures",
    "Australian public text archive",
    "Australian supernatural",
    "Australian supernatural folklore",
    "supernatural humanoid narratives",
    "Australian supernatural humanoids",
    "source-grounded archive",
    "digital humanities",
    "Australian folklore research",
    "Yowie records",
    "bunyip public texts",
    "Australian apparition records",
    "Australian ghost records",
    "Australian ghosts",
    "Australian apparitions",
    "spirit-person narratives",
    "public record map",
    "mapped public records",
    "Yowie public records",
    "bunyip folklore records",
    "Australian public text research",
    "public source register",
  ],
  routeMetadata: [
    {
      path: "/",
      title: "AusFigures",
      description:
        "Explore a source-grounded map of Australian supernatural humanoid public records, including Yowie, bunyip, apparition, ghost, spirit-person, and giant narratives. Public sources are not proof.",
      priority: 1.0,
      changeFrequency: "monthly",
    },
    {
      path: "/map",
      canonicalPath: "/",
      title: "AusFigures Map",
      description:
        "Map view for Australian supernatural humanoid public records in AusFigures. Markers identify public display locations, not supernatural proof, habitats, or populations.",
      priority: 0.0,
      changeFrequency: "monthly",
    },
    {
      path: "/dashboard",
      title: "Research Dashboard",
      description:
        "Research dashboard for the AusFigures public-text corpus, with period, source-family, narrative-type, figure-label, and mapped-record coverage for Australian supernatural humanoid records.",
      priority: 0.8,
      changeFrequency: "monthly",
    },
    {
      path: "/density",
      title: "Density Explorer",
      description:
        "Density explorer for Australian supernatural public-text records, comparing source, query, figure, period, and mapped-location signals across AusFigures.",
      priority: 0.7,
      changeFrequency: "monthly",
    },
    {
      path: "/source",
      title: "Source Register",
      description:
        "Source register for AusFigures, listing public source organisations, source families, and public metadata context behind Australian supernatural humanoid records.",
      priority: 0.8,
      changeFrequency: "monthly",
    },
    {
      path: "/about",
      title: "About AusFigures",
      description:
        "About AusFigures: scope, methods, source policy, mapping limits, and ethical interpretation rules for a source-grounded Australian supernatural public-text archive.",
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

export function canonicalPathForRoute(route: (typeof siteConfig.routeMetadata)[number]) {
  return "canonicalPath" in route ? route.canonicalPath : route.path;
}

export function metadataForRoute(path: SiteRoutePath): Metadata {
  const route = routeConfig(path);
  const title = route.title;
  const description = route.description;
  const metaTitle = brandedTitle(title);
  const canonicalPath = canonicalPathForRoute(route);
  const metadataTitle: Metadata["title"] = title.includes(SITE.name) ? { absolute: title } : title;

  return {
    title: metadataTitle,
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
