import type { MetadataRoute } from "next";
import { SITE, absoluteUrl, siteConfig } from "@/lib/site";

const releaseDate = new Date(`${siteConfig.releaseDate}T00:00:00.000Z`);

export default function sitemap(): MetadataRoute.Sitemap {
  return siteConfig.routeMetadata
    .filter((route) => (SITE.routes as readonly string[]).includes(route.path))
    .map((route) => ({
      url: absoluteUrl(route.path),
      lastModified: releaseDate,
      changeFrequency: route.changeFrequency,
      priority: route.priority,
    }));
}
