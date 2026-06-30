import type { MetadataRoute } from "next";
import { SITE, absoluteUrl, siteConfig } from "@/lib/site";
import { seoTopics, topicPath } from "@/lib/seo-topics";

const releaseDate = new Date(`${siteConfig.releaseDate}T00:00:00.000Z`);

export default function sitemap(): MetadataRoute.Sitemap {
  const primaryRoutes = siteConfig.routeMetadata
    .filter((route) => (SITE.routes as readonly string[]).includes(route.path))
    .filter((route) => !("canonicalPath" in route))
    .map((route) => ({
      url: absoluteUrl(route.path),
      lastModified: releaseDate,
      changeFrequency: route.changeFrequency,
      priority: route.priority,
    }));

  const topicRoutes = seoTopics.map((topic) => ({
    url: absoluteUrl(topicPath(topic.slug)),
    lastModified: releaseDate,
    changeFrequency: "monthly" as const,
    priority: 0.62,
  }));

  return [
    ...primaryRoutes,
    {
      url: absoluteUrl("/topics"),
      lastModified: releaseDate,
      changeFrequency: "monthly" as const,
      priority: 0.66,
    },
    ...topicRoutes,
  ];
}
