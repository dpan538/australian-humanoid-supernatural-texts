import type { Metadata } from "next";

export const SITE = {
  name: "AusFigures",
  fullTitle: "Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters",
  domain: "ausfigures.com",
  url: "https://ausfigures.com",
  canonicalOrigin: "https://ausfigures.com",
  repositoryUrl: "https://github.com/dpan538/australian-humanoid-supernatural-texts",
  primaryRoute: "/dashboard",
  routes: ["/dashboard", "/map", "/density", "/source", "/about"],
  description:
    "A source-grounded public-text archive and research display system for Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings.",
} as const;

export const siteConfig = {
  ...SITE,
  siteUrl: SITE.url,
  siteName: SITE.name,
  shortDescription: SITE.description,
  creator: "Dai Pan",
  locale: "en_AU",
  releaseDate: "2026-06-29",
  routeMetadata: [
    {
      path: "/dashboard",
      title: "Dashboard",
      description:
        "Corpus overview for AusFigures, a source-grounded public-text archive of Australian supernatural humanoid narratives, source families, narrative types, periods, and mapped-record aggregates.",
      priority: 1.0,
      changeFrequency: "monthly",
    },
    {
      path: "/map",
      title: "Map",
      description:
        "Verified mapped public records in AusFigures. Map markers represent public display locations for records, not proof, habitats, or populations.",
      priority: 0.7,
      changeFrequency: "monthly",
    },
    {
      path: "/density",
      title: "Density",
      description:
        "Source, query, and figure-density views for comparing corpus signals in the AusFigures public-text archive.",
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
      title: "About",
      description:
        "Scope, methods, source policy, mapping limits, and ethical interpretation rules for AusFigures.",
      priority: 0.8,
      changeFrequency: "monthly",
    },
  ],
} as const;

export type SiteRoutePath = (typeof SITE.routes)[number];

export function absoluteUrl(path = "/") {
  return new URL(path, SITE.canonicalOrigin).toString();
}

export function routeConfig(path: SiteRoutePath) {
  return siteConfig.routeMetadata.find((route) => route.path === path) ?? siteConfig.routeMetadata[0];
}

export function metadataForRoute(path: SiteRoutePath): Metadata {
  const route = routeConfig(path);
  const title = route.title;
  const description = route.description;

  return {
    title,
    description,
    alternates: {
      canonical: absoluteUrl(route.path),
    },
    robots: {
      index: true,
      follow: true,
    },
    openGraph: {
      title: `${title} | ${siteConfig.siteName}`,
      description,
      url: absoluteUrl(route.path),
      siteName: siteConfig.siteName,
      locale: siteConfig.locale,
      type: "website",
    },
    twitter: {
      card: "summary",
      title: `${title} | ${siteConfig.siteName}`,
      description,
    },
  };
}
