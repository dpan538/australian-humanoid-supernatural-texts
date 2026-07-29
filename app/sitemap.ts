import type { MetadataRoute } from "next";
import {
  indexableRecords,
  encyclopediaFigureGroups,
  loadArchiveData,
  narrativeTypeGroups,
  periodGroups,
  placeGroups,
  recordsIndexPageCount,
  sourceGroups,
} from "@/lib/archive-catalog";
import {
  figurePath,
  narrativeTypePath,
  periodPath,
  placePath,
  recordPath,
  recordsPagePath,
  sourcePath,
} from "@/lib/archive-routing";
import { absoluteUrl, siteConfig } from "@/lib/site";

const STATIC_INDEX_PATHS = [
  "/",
  "/dashboard",
  "/density",
  "/source",
  "/about",
  "/records",
  "/narrative-types",
  "/figures",
  "/sources",
  "/places",
  "/periods",
  "/data",
  "/cite",
] as const;

const STATIC_PRIORITIES: Record<(typeof STATIC_INDEX_PATHS)[number], number> = {
  "/": 1,
  "/dashboard": 0.82,
  "/density": 0.72,
  "/source": 0.82,
  "/about": 0.82,
  "/records": 0.8,
  "/narrative-types": 0.64,
  "/figures": 0.94,
  "/sources": 0.64,
  "/places": 0.62,
  "/periods": 0.62,
  "/data": 0.58,
  "/cite": 0.58,
};

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const data = await loadArchiveData();
  const lastModified = new Date(
    Math.max(
      new Date(data.generated_at).valueOf(),
      new Date(`${siteConfig.contentUpdatedDate}T00:00:00.000Z`).valueOf(),
    ),
  );
  const entry = (
    path: string,
    changeFrequency: "weekly" | "monthly" | "yearly" = "monthly",
    priority = 0.5,
  ) => ({
    url: absoluteUrl(path),
    lastModified,
    changeFrequency,
    priority,
  });

  const staticRoutes = STATIC_INDEX_PATHS.map((path) =>
    entry(path, path === "/" || path === "/records" || path === "/figures" ? "weekly" : "monthly", STATIC_PRIORITIES[path]),
  );
  const recordPaginationRoutes = Array.from(
    { length: Math.max(0, recordsIndexPageCount(data) - 1) },
    (_, index) => entry(recordsPagePath(index + 2), "weekly", 0.46),
  );
  const recordRoutes = indexableRecords(data).map((record) => entry(recordPath(record), "yearly", 0.42));
  const narrativeRoutes = narrativeTypeGroups(data).map((group) =>
    entry(narrativeTypePath(group.key), "monthly", 0.6),
  );
  const figureRoutes = encyclopediaFigureGroups(data)
    .filter((group) => group.indexEligible)
    .map((group) => entry(figurePath(group.slug), "monthly", 0.74));
  const sourceRoutes = sourceGroups(data)
    .filter((group) => group.records.length >= 2)
    .map((group) => entry(sourcePath(group.sourceId, group.label), "monthly", 0.58));
  const placeRoutes = placeGroups(data).map((group) => entry(placePath(group.key), "monthly", 0.56));
  const periodRoutes = periodGroups(data).map((group) => entry(periodPath(group.key), "monthly", 0.56));

  return [
    ...staticRoutes,
    ...recordPaginationRoutes,
    ...narrativeRoutes,
    ...figureRoutes,
    ...sourceRoutes,
    ...placeRoutes,
    ...periodRoutes,
    ...recordRoutes,
  ];
}
