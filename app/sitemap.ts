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
  humanizeArchiveCode,
  narrativeTypePath,
  periodPath,
  placePath,
  recordPath,
  recordsPagePath,
  sourcePath,
} from "@/lib/archive-routing";
import { absoluteUrl, siteConfig, socialCardImageMetadata } from "@/lib/site";

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

const STATIC_SOCIAL_COPY: Record<(typeof STATIC_INDEX_PATHS)[number], { title: string; description: string }> = {
  "/": {
    title: "Australian Supernatural Humanoid Public-Text Archive",
    description: "Source-grounded public texts, mapped display locations, figures, periods, and source context across Australia.",
  },
  "/dashboard": {
    title: "AusFigures Research Dashboard",
    description: "Corpus coverage across records, mapped locations, figures, source families, narrative types, and historical periods.",
  },
  "/density": {
    title: "AusFigures Density Explorer",
    description: "Time, source, figure, and mapped-location signals in the Australian supernatural public-text archive.",
  },
  "/source": {
    title: "AusFigures Source Register",
    description: "Public source organisations, source families, roles, and metadata context represented in the archive.",
  },
  "/about": {
    title: "About AusFigures",
    description: "Scope, method, source policy, mapping limits, ethics, and interpretation guidance for AusFigures.",
  },
  "/records": {
    title: "Australian Supernatural Humanoid Public-Text Records",
    description: "Search-ready source-grounded records across encounters, apparitions, legends, beliefs, and retellings.",
  },
  "/narrative-types": {
    title: "Supernatural Humanoid Narrative Types",
    description: "Browse the public-text archive by narrative form and source framing.",
  },
  "/figures": {
    title: "Australian Supernatural Humanoid Encyclopedia",
    description: "Search figures, aliases, public records, sources, places, periods, and related archive classifications.",
  },
  "/sources": {
    title: "Public Source Organisations and Collections",
    description: "Browse repositories, institutional pages, books, archives, and public metadata collections.",
  },
  "/places": {
    title: "Australian Places in Supernatural Humanoid Public Texts",
    description: "Browse reviewed public-text place associations by Australian state and territory.",
  },
  "/periods": {
    title: "Periods in Australian Supernatural Humanoid Public Texts",
    description: "Browse the archive by publication and source period from 1825 to the present.",
  },
  "/data": {
    title: "AusFigures Data, Coverage, and Index Policy",
    description: "Public data scope, page inventory, provenance boundaries, and machine-readable access.",
  },
  "/cite": {
    title: "Cite AusFigures",
    description: "Citation, attribution, version, scope, and reuse guidance for the AusFigures public archive.",
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
    changeFrequency: "weekly" | "monthly" | "yearly" = "monthly",
    priority = 0.5,
    image?: string,
  ) => ({
    url: absoluteUrl(path),
    lastModified,
    changeFrequency,
    priority,
    // Next's sitemap serializer writes image URLs verbatim. Query-string
    // separators therefore need XML escaping or they make the whole sitemap
    // malformed (for example, a bare `&description=` in <image:loc>).
    ...(image ? { images: [escapeXmlUrl(image)] } : {}),
  });

  const staticRoutes = STATIC_INDEX_PATHS.map((path) => {
    const copy = STATIC_SOCIAL_COPY[path];
    const image = socialCardImageMetadata({
      title: copy.title,
      description: copy.description,
      eyebrow: "AUSFIGURES RESEARCH INDEX",
    }).url;
    return entry(
      path,
      path === "/" || path === "/records" || path === "/figures" ? "weekly" : "monthly",
      STATIC_PRIORITIES[path],
      image,
    );
  });
  const recordPaginationRoutes = Array.from(
    { length: Math.max(0, recordsIndexPageCount(data) - 1) },
    (_, index) => {
      const page = index + 2;
      return entry(
        recordsPagePath(page),
        "weekly",
        0.46,
        socialCardImageMetadata({
          title: `Australian Supernatural Humanoid Public-Text Records — Page ${page}`,
          description: `Page ${page} of the search-ready AusFigures public-text record index.`,
          eyebrow: "PUBLIC RECORD INDEX",
          tone: "paper",
        }).url,
      );
    },
  );
  const recordRoutes = indexableRecords(data).map((record) => {
    const description = compactText(
      record.snippet || `${record.title} is a source-grounded public-text record in the AusFigures archive.`,
      176,
    );
    const image = socialCardImageMetadata({
      title: `${record.title} — Public-Text Record #${record.record_id}`,
      description,
      eyebrow: "PUBLIC-TEXT RECORD",
      metric: `#${record.record_id}`,
      tone: "paper",
    }).url;
    return entry(recordPath(record), "yearly", 0.42, image);
  });
  const narrativeRoutes = narrativeTypeGroups(data).map((group) =>
    entry(
      narrativeTypePath(group.key),
      "monthly",
      0.6,
      socialCardImageMetadata({
        title: `${group.label} in Australian Public Texts`,
        description: `${group.records.length} source-grounded public-text records classified as ${group.label.toLowerCase()}.`,
        eyebrow: "NARRATIVE TYPE",
        metric: `${group.records.length.toLocaleString("en-AU")} records`,
        tone: "ink",
      }).url,
    ),
  );
  const figureRoutes = encyclopediaFigureGroups(data)
    .filter((group) => group.indexEligible)
    .map((group) => entry(
      figurePath(group.slug),
      "monthly",
      0.74,
      socialCardImageMetadata({
        title: `${group.label} — Australian Supernatural Humanoid Encyclopedia`,
        description: `${group.records.length} connected public records, aliases, sources, places, periods, and related classifications.`,
        eyebrow: "FIGURE ENCYCLOPEDIA",
        metric: `${group.records.length.toLocaleString("en-AU")} records`,
        tone: "blue",
      }).url,
    ));
  const sourceRoutes = sourceGroups(data)
    .filter((group) => group.records.length >= 2)
    .map((group) => {
      const sourceType = humanizeArchiveCode(group.source?.source_type || group.records[0]?.source_type);
      return entry(
        sourcePath(group.sourceId, group.label),
        "monthly",
        0.58,
        socialCardImageMetadata({
          title: `${group.label} — ${sourceType} Records`,
          description: `Public source context for ${group.records.length} search-ready AusFigures records.`,
          eyebrow: "PUBLIC SOURCE COLLECTION",
          metric: `${group.records.length.toLocaleString("en-AU")} records`,
          tone: "sage",
        }).url,
      );
    });
  const placeRoutes = placeGroups(data).map((group) => entry(
    placePath(group.key),
    "monthly",
    0.56,
    socialCardImageMetadata({
      title: `${group.label} Supernatural Humanoid Public-Text Records`,
      description: `Reviewed place associations for ${group.records.length} source-grounded public-text records.`,
      eyebrow: "NARRATIVE GEOGRAPHY",
      metric: `${group.records.length.toLocaleString("en-AU")} records`,
      tone: "clay",
    }).url,
  ));
  const periodRoutes = periodGroups(data).map((group) => entry(
    periodPath(group.key),
    "monthly",
    0.56,
    socialCardImageMetadata({
      title: `${group.label} Australian Supernatural Public Texts`,
      description: `${group.records.length} search-ready public-text records grouped by source period.`,
      eyebrow: "SOURCE PERIOD",
      metric: `${group.records.length.toLocaleString("en-AU")} records`,
      tone: "ochre",
    }).url,
  ));

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

function compactText(value: string, limit: number) {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trimEnd()}…` : text;
}

function escapeXmlUrl(value: string) {
  return value.replaceAll("&", "&amp;");
}
