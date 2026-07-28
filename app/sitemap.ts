import type { MetadataRoute } from "next";
import {
  indexableRecords,
  labelGroups,
  loadArchiveData,
  narrativeTypeGroups,
  periodGroups,
  placeGroups,
  recordsIndexPageCount,
  sourceGroups,
} from "@/lib/archive-catalog";
import {
  labelPath,
  narrativeTypePath,
  periodPath,
  placePath,
  recordPath,
  recordsPagePath,
  sourcePath,
} from "@/lib/archive-routing";
import { seoTopics, topicPath } from "@/lib/seo-topics";
import { absoluteUrl, siteConfig } from "@/lib/site";

const STATIC_INDEX_PATHS = [
  "/",
  "/dashboard",
  "/density",
  "/source",
  "/about",
  "/topics",
  "/records",
  "/narrative-types",
  "/labels",
  "/sources",
  "/places",
  "/periods",
  "/data",
  "/cite",
] as const;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const data = await loadArchiveData();
  const lastModified = new Date(
    Math.max(
      new Date(data.generated_at).valueOf(),
      new Date(`${siteConfig.contentUpdatedDate}T00:00:00.000Z`).valueOf(),
    ),
  );
  const entry = (path: string, changeFrequency: "weekly" | "monthly" | "yearly" = "monthly") => ({
    url: absoluteUrl(path),
    lastModified,
    changeFrequency,
  });

  const staticRoutes = STATIC_INDEX_PATHS.map((path) => entry(path, path === "/" || path === "/records" ? "weekly" : "monthly"));
  const topicRoutes = seoTopics.map((topic) => entry(topicPath(topic.slug), "monthly"));
  const recordPaginationRoutes = Array.from(
    { length: Math.max(0, recordsIndexPageCount(data) - 1) },
    (_, index) => entry(recordsPagePath(index + 2), "weekly"),
  );
  const recordRoutes = indexableRecords(data).map((record) => entry(recordPath(record), "yearly"));
  const narrativeRoutes = narrativeTypeGroups(data).map((group) => entry(narrativeTypePath(group.key), "monthly"));
  const labelRoutes = labelGroups(data).map((group) => entry(labelPath(group.key), "monthly"));
  const sourceRoutes = sourceGroups(data)
    .filter((group) => group.records.length >= 2)
    .map((group) => entry(sourcePath(group.sourceId, group.label), "monthly"));
  const placeRoutes = placeGroups(data).map((group) => entry(placePath(group.key), "monthly"));
  const periodRoutes = periodGroups(data).map((group) => entry(periodPath(group.key), "monthly"));

  return [
    ...staticRoutes,
    ...topicRoutes,
    ...recordPaginationRoutes,
    ...narrativeRoutes,
    ...labelRoutes,
    ...sourceRoutes,
    ...placeRoutes,
    ...periodRoutes,
    ...recordRoutes,
  ];
}
