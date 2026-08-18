import type { MetadataRoute } from "next";
import { encyclopediaFigureGroups, loadArchiveData } from "@/lib/archive-catalog";
import { figurePath } from "@/lib/archive-routing";
import {
  INDEXED_FIGURE_SLUGS,
  INDEXED_STATIC_PATHS,
} from "@/lib/search-index-policy";
import { absoluteUrl, siteConfig, socialCardImageMetadata } from "@/lib/site";

const STATIC_PRIORITIES: Record<(typeof INDEXED_STATIC_PATHS)[number], number> = {
  "/": 1,
  "/dashboard": 0.82,
  "/density": 0.72,
  "/source": 0.82,
  "/about": 0.82,
  "/figures": 0.94,
  "/data": 0.58,
  "/cite": 0.58,
};

const STATIC_SOCIAL_COPY: Record<
  (typeof INDEXED_STATIC_PATHS)[number],
  { title: string; description: string }
> = {
  "/": {
    title: "Australian Supernatural Humanoid Public-Text Archive",
    description: "Source-grounded public texts and mapped display locations across Australia.",
  },
  "/dashboard": {
    title: "AusFigures Research Dashboard",
    description: "Corpus coverage across records, figures, sources, periods, and mapped locations.",
  },
  "/density": {
    title: "AusFigures Density Explorer",
    description: "Time, source, figure, and mapped-location signals in the public-text archive.",
  },
  "/source": {
    title: "AusFigures Source Register",
    description: "The canonical register of public source organisations and source families.",
  },
  "/about": {
    title: "About AusFigures",
    description: "Scope, method, source policy, mapping limits, ethics, and interpretation guidance.",
  },
  "/figures": {
    title: "Australian Supernatural Humanoid Encyclopedia",
    description: "Search figures, aliases, records, sources, places, periods, and classifications.",
  },
  "/data": {
    title: "AusFigures Data, Coverage, and Index Policy",
    description: "Public data scope, provenance boundaries, and machine-readable access.",
  },
  "/cite": {
    title: "Cite AusFigures",
    description: "Citation, attribution, version, scope, and reuse guidance for the archive.",
  },
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
    changeFrequency: "weekly" | "monthly" = "monthly",
    priority = 0.5,
    image?: string,
  ) => ({
    url: absoluteUrl(path),
    lastModified,
    changeFrequency,
    priority,
    ...(image ? { images: [escapeXmlUrl(image)] } : {}),
  });

  const staticRoutes = INDEXED_STATIC_PATHS.map((path) => {
    const copy = STATIC_SOCIAL_COPY[path];
    return entry(
      path,
      path === "/" || path === "/figures" ? "weekly" : "monthly",
      STATIC_PRIORITIES[path],
      socialCardImageMetadata({
        title: copy.title,
        description: copy.description,
        eyebrow: "AUSFIGURES RESEARCH INDEX",
      }).url,
    );
  });

  const promotedFigures = new Set<string>(INDEXED_FIGURE_SLUGS);
  const figureRoutes = encyclopediaFigureGroups(data)
    .filter((group) => group.indexEligible && promotedFigures.has(group.slug))
    .map((group) =>
      entry(
        figurePath(group.slug),
        "monthly",
        0.78,
        socialCardImageMetadata({
          title: `${group.label} — Australian Supernatural Humanoid Encyclopedia`,
          description: `${group.records.length} connected public records, sources, places, periods, and related classifications.`,
          eyebrow: "FIGURE ENCYCLOPEDIA",
          metric: `${group.records.length.toLocaleString("en-AU")} records`,
          tone: "blue",
        }).url,
      ),
    );

  return [...staticRoutes, ...figureRoutes];
}

function escapeXmlUrl(value: string) {
  return value.replaceAll("&", "&amp;");
}
