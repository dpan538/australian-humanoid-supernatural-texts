import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const projectRoot = process.cwd();
const dataPath = path.join(projectRoot, "public", "data", "frontend-data.json");
const data = JSON.parse(await readFile(dataPath, "utf8"));

const pageEligible = (record) =>
  record.include_status !== "control_only" &&
  record.include_status !== "exclude_core" &&
  record.ontology_code !== "non_humanoid_control" &&
  Boolean(record.title && record.url && record.source_name);

const indexEligible = (record) =>
  pageEligible(record) &&
  (record.ethics_flag === "ok_public" || String(record.ethics_flag || "").startsWith("public_"));

const pageRecords = data.records.filter(pageEligible);
const indexRecords = data.records.filter(indexEligible);
const groupCount = (records, keyFor) => new Set(records.map(keyFor).filter(Boolean)).size;
const groupedCounts = (records, keyFor) => {
  const counts = new Map();
  for (const record of records) {
    const key = keyFor(record);
    if (!key) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
};
const labelKey = (record) =>
  String(record.canonical_figure_guess || record.canonical_figure || "")
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
const normalizeFigureLabel = (value) =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[_\s]+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
const figureAliases = new Map([
  ["yahoo", "yowie"],
  ["ghosts", "ghost"],
  ["apparition", "ghost"],
  ["apparitions", "ghost"],
  ["spirits", "spirit"],
  ["spirit-person", "spirit"],
  ["devils", "devil"],
  ["giants", "giant"],
  ["ogre", "giant"],
  ["ogres", "giant"],
  ["bunyips", "bunyip"],
  ["medicine-men", "medicine-man"],
]);
const figureSlug = (value) => {
  const normalized = normalizeFigureLabel(value) || "uncoded-figure";
  return figureAliases.get(normalized) || normalized;
};
const taxonomyFigurePageEligible = (figure) =>
  figure.include_status !== "control_only" &&
  figure.include_status !== "exclude_core" &&
  figure.humanoid_degree !== "non_humanoid";

const recordIndexPages = Math.max(1, Math.ceil(indexRecords.length / 100));
const narrativeTypePages = groupCount(indexRecords, (record) => record.ontology_code);
const labelVocabularyGroups = [...groupedCounts(indexRecords, labelKey).values()].filter((count) => count >= 4).length;
const sourceCounts = groupedCounts(indexRecords, (record) => record.source_id);
const sourcePages = sourceCounts.size;
const indexedSourcePages = [...sourceCounts.values()].filter((count) => count >= 2).length;
const placePages = groupCount(indexRecords, (record) => record.state_territory);
const periodPages = data.date_bands.filter((period) =>
  indexRecords.some((record) => record.date_band === period.id),
).length;
const indexedFigureSlugs = new Set(
  indexRecords
    .map((record) => figureSlug(record.canonical_figure_guess || record.canonical_figure))
    .filter(Boolean),
);
const figurePageSlugs = new Set([
  ...indexedFigureSlugs,
  ...data.figures
    .filter(taxonomyFigurePageEligible)
    .map((figure) => figureSlug(figure.canonical_name))
    .filter(Boolean),
]);
const staticContentPaths = 14;
const staticIndexPaths = 13;

const inventory = {
  data_generated_at: data.generated_at,
  public_data_records: data.records.length,
  record_pages: pageRecords.length,
  indexable_record_pages: indexRecords.length,
  review_only_record_pages: pageRecords.length - indexRecords.length,
  record_index_pages: recordIndexPages,
  narrative_type_pages: narrativeTypePages,
  label_vocabulary_groups: labelVocabularyGroups,
  figure_encyclopedia_pages: figurePageSlugs.size,
  indexed_figure_encyclopedia_pages: indexedFigureSlugs.size,
  taxonomy_only_figure_pages: figurePageSlugs.size - indexedFigureSlugs.size,
  source_pages: sourcePages,
  indexed_source_pages: indexedSourcePages,
  place_pages: placePages,
  period_pages: periodPages,
  intended_content_pages:
    staticContentPaths +
    pageRecords.length +
    Math.max(0, recordIndexPages - 1) +
    narrativeTypePages +
    figurePageSlugs.size +
    sourcePages +
    placePages +
    periodPages,
  intended_sitemap_urls:
    staticIndexPaths +
    Math.max(0, recordIndexPages - 1) +
    narrativeTypePages +
    indexedFigureSlugs.size +
    indexedSourcePages +
    placePages +
    periodPages +
    indexRecords.length,
};

const textMatch = (html, pattern) => html.match(pattern)?.[1]?.trim() || "";
const decodeText = (value) =>
  value
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&#x2F;/g, "/");

function metaContent(html, attribute, value) {
  const tags = html.match(/<meta\b[^>]*>/gi) || [];
  for (const tag of tags) {
    const attributeValue = textMatch(
      tag,
      new RegExp(`${attribute}=["']([^"']+)["']`, "i"),
    );
    if (attributeValue.toLowerCase() !== value.toLowerCase()) {
      continue;
    }
    return decodeText(textMatch(tag, /content=["']([^"']*)["']/i));
  }
  return "";
}

function structuredDataScripts(html) {
  return [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)]
    .filter((match) => /type=["']application\/ld\+json["']/i.test(match[1]))
    .map((match) => match[2].trim());
}

async function listFiles(directory, suffix) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await listFiles(absolutePath, suffix));
    } else if (entry.name.endsWith(suffix)) {
      files.push(absolutePath);
    }
  }
  return files;
}

function routeForHtml(buildRoot, filePath) {
  const relativePath = path.relative(buildRoot, filePath).split(path.sep).join("/");
  if (relativePath === "index.html") return "/";
  return `/${relativePath.replace(/\.html$/, "").replace(/\/index$/, "")}`;
}

function inspectHtml(route, html) {
  const title = decodeText(textMatch(html, /<title[^>]*>([\s\S]*?)<\/title>/i));
  const description = metaContent(html, "name", "description");
  const canonical = textMatch(html, /<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["'][^>]*>/i);
  const robots = metaContent(html, "name", "robots");
  const openGraph = {
    title: metaContent(html, "property", "og:title"),
    description: metaContent(html, "property", "og:description"),
    type: metaContent(html, "property", "og:type"),
    url: metaContent(html, "property", "og:url"),
    image: metaContent(html, "property", "og:image"),
    imageAlt: metaContent(html, "property", "og:image:alt"),
    siteName: metaContent(html, "property", "og:site_name"),
  };
  const twitter = {
    card: metaContent(html, "name", "twitter:card"),
    title: metaContent(html, "name", "twitter:title"),
    description: metaContent(html, "name", "twitter:description"),
    image: metaContent(html, "name", "twitter:image"),
    imageAlt: metaContent(html, "name", "twitter:image:alt"),
  };
  const jsonLdScripts = structuredDataScripts(html);
  const structuredDataValid = jsonLdScripts.length > 0 && jsonLdScripts.every((value) => {
    try {
      JSON.parse(value);
      return true;
    } catch {
      return false;
    }
  });
  const visibleText = decodeText(
    html
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
      .replace(/<noscript\b[^>]*>[\s\S]*?<\/noscript>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim(),
  );
  return {
    route,
    title,
    description,
    canonical,
    robots,
    noindex: /\bnoindex\b/i.test(robots),
    hasH1: /<h1\b[^>]*>[\s\S]*?<\/h1>/i.test(html),
    hasStructuredData: jsonLdScripts.length > 0,
    structuredDataValid,
    openGraph,
    twitter,
    completeOpenGraph: Boolean(
      openGraph.title &&
      openGraph.description &&
      openGraph.type &&
      openGraph.url &&
      openGraph.image &&
      openGraph.imageAlt &&
      openGraph.siteName
    ),
    completeTwitterCard: Boolean(
      twitter.card &&
      twitter.title &&
      twitter.description &&
      twitter.image &&
      twitter.imageAlt
    ),
    hasOpenSearchDiscovery: /<link\b[^>]*rel=["']search["'][^>]*type=["']application\/opensearchdescription\+xml["'][^>]*>/i.test(html),
    visibleTextLength: visibleText.length,
  };
}

function duplicatePageValues(pages, valueFor) {
  const groups = new Map();
  for (const page of pages) {
    const value = valueFor(page);
    if (!value) continue;
    const routes = groups.get(value) || [];
    routes.push(page.route);
    groups.set(value, routes);
  }
  return [...groups.values()].filter((routes) => routes.length > 1).flat();
}

async function auditBuildOutput() {
  const buildRoot = path.join(projectRoot, ".next", "server", "app");
  const htmlFiles = await listFiles(buildRoot, ".html");
  const pages = await Promise.all(
    htmlFiles.map(async (filePath) => inspectHtml(routeForHtml(buildRoot, filePath), await readFile(filePath, "utf8"))),
  );
  const frameworkErrorRoutes = new Set(["/_not-found", "/_global-error"]);
  const contentPages = pages.filter((page) => !frameworkErrorRoutes.has(page.route));
  const sitemapXml = await readFile(path.join(buildRoot, "sitemap.xml.body"), "utf8");
  const robotsText = await readFile(path.join(buildRoot, "robots.txt.body"), "utf8");
  const openSearchText = await readFile(path.join(buildRoot, "opensearch.xml.body"), "utf8");
  const sitemapUrls = [...sitemapXml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => decodeText(match[1]));
  const sitemapImages = [...sitemapXml.matchAll(/<image:loc>([^<]+)<\/image:loc>/g)].map((match) => decodeText(match[1]));
  const sitemapPaths = new Set(sitemapUrls.map((url) => new URL(url).pathname.replace(/\/$/, "") || "/"));
  const pageByRoute = new Map(contentPages.map((page) => [page.route, page]));
  const sitemapMissingHtml = [...sitemapPaths].filter((route) => !pageByRoute.has(route));
  const indexablePages = contentPages.filter((page) => !page.noindex);
  const indexableMissingSitemap = indexablePages
    .filter((page) => !sitemapPaths.has(page.route))
    .map((page) => page.route);
  const sitemapNoindexPages = [...sitemapPaths]
    .filter((route) => pageByRoute.get(route)?.noindex);
  const legacySitemapPaths = [...sitemapPaths]
    .filter((route) => route === "/labels" || route.startsWith("/labels/") || route === "/topics" || route.startsWith("/topics/"));
  const canonicalTargets = contentPages
    .map((page) => page.canonical)
    .filter(Boolean)
    .map((url) => new URL(url).pathname.replace(/\/$/, "") || "/");
  const missingCanonicalTargets = canonicalTargets.filter((route) => !pageByRoute.has(route));
  const openSearchValid =
    /<OpenSearchDescription\b[^>]*xmlns="http:\/\/a9\.com\/-\/spec\/opensearch\/1\.1\/"/i.test(openSearchText) &&
    /<Url\b[^>]*type="text\/html"[^>]*\{searchTerms\}/i.test(openSearchText) &&
    /<Url\b[^>]*type="application\/x-suggestions\+json"[^>]*\{searchTerms\}/i.test(openSearchText);
  const failures = {
    malformed_sitemap_xml_entities: /&(?!(?:amp|lt|gt|quot|apos);|#\d+;|#x[\da-f]+;)/i.test(sitemapXml)
      ? ["/sitemap.xml"]
      : [],
    missing_title: contentPages.filter((page) => !page.title).map((page) => page.route),
    missing_description: contentPages.filter((page) => !page.description).map((page) => page.route),
    missing_canonical: contentPages.filter((page) => !page.canonical).map((page) => page.route),
    missing_robots_meta: contentPages.filter((page) => !page.robots).map((page) => page.route),
    missing_h1: contentPages.filter((page) => !page.hasH1).map((page) => page.route),
    invalid_structured_data: contentPages.filter((page) => !page.structuredDataValid).map((page) => page.route),
    incomplete_open_graph: contentPages.filter((page) => !page.completeOpenGraph).map((page) => page.route),
    incomplete_twitter_card: contentPages.filter((page) => !page.completeTwitterCard).map((page) => page.route),
    missing_opensearch_discovery: contentPages.filter((page) => !page.hasOpenSearchDiscovery).map((page) => page.route),
    non_content_specific_social_image: contentPages
      .filter((page) => !page.openGraph.image.includes("/social-card?"))
      .map((page) => page.route),
    duplicate_indexable_titles: duplicatePageValues(indexablePages, (page) => page.title),
    duplicate_indexable_canonicals: duplicatePageValues(indexablePages, (page) => page.canonical),
    open_graph_canonical_mismatch: contentPages
      .filter((page) => page.canonical && page.openGraph.url !== page.canonical)
      .map((page) => page.route),
    invalid_canonical_origin: contentPages
      .filter(
        (page) =>
          page.canonical &&
          page.canonical !== "https://ausfigures.com" &&
          !page.canonical.startsWith("https://ausfigures.com/"),
      )
      .map((page) => page.route),
    thin_server_html: contentPages.filter((page) => page.visibleTextLength < 120).map((page) => page.route),
    sitemap_missing_html: sitemapMissingHtml,
    indexable_missing_sitemap: indexableMissingSitemap,
    sitemap_contains_noindex: sitemapNoindexPages,
    sitemap_contains_legacy_taxonomy: legacySitemapPaths,
    missing_canonical_targets: [...new Set(missingCanonicalTargets)],
    invalid_opensearch_document: openSearchValid ? [] : ["/opensearch.xml"],
    sitemap_entries_without_social_image:
      sitemapImages.length === sitemapUrls.length ? [] : [`${sitemapUrls.length - sitemapImages.length} entries`],
  };
  const failureCount = Object.values(failures).reduce((total, routes) => total + routes.length, 0);
  return {
    generated_html_pages: pages.length,
    content_html_pages: contentPages.length,
    indexable_html_pages: indexablePages.length,
    crawlable_noindex_pages: contentPages.filter((page) => page.noindex).length,
    pages_with_structured_data: contentPages.filter((page) => page.hasStructuredData).length,
    pages_with_valid_structured_data: contentPages.filter((page) => page.structuredDataValid).length,
    pages_with_complete_open_graph: contentPages.filter((page) => page.completeOpenGraph).length,
    pages_with_complete_twitter_cards: contentPages.filter((page) => page.completeTwitterCard).length,
    sitemap_urls: sitemapUrls.length,
    sitemap_unique_urls: new Set(sitemapUrls).size,
    sitemap_images: sitemapImages.length,
    sitemap_unique_images: new Set(sitemapImages).size,
    opensearch_valid: openSearchValid,
    robots_allows_root: /User-agent:\s*\*[\s\S]*?Allow:\s*\/(?:\s|$)/i.test(robotsText),
    robots_has_disallow: /^Disallow:/im.test(robotsText),
    robots_declares_sitemap: /Sitemap:\s*https:\/\/ausfigures\.com\/sitemap\.xml/i.test(robotsText),
    failure_count: failureCount,
    failures,
  };
}

if (process.argv.includes("--build")) {
  inventory.build_crawlability = await auditBuildOutput();
}

if (process.argv.includes("--live")) {
  const [sitemapResponse, robotsResponse, sourceResponse, dashboardResponse, figuresResponse] = await Promise.all([
    fetch("https://ausfigures.com/sitemap.xml"),
    fetch("https://ausfigures.com/robots.txt"),
    fetch("https://ausfigures.com/source"),
    fetch("https://ausfigures.com/dashboard"),
    fetch("https://ausfigures.com/figures"),
  ]);
  const [xml, liveRobots, liveSource, liveDashboard, liveFigures] = await Promise.all([
    sitemapResponse.text(),
    robotsResponse.text(),
    sourceResponse.text(),
    dashboardResponse.text(),
    figuresResponse.text(),
  ]);
  const liveSitemapUrls = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => decodeText(match[1]));
  const liveSitemapPaths = liveSitemapUrls.map((url) => new URL(url).pathname);
  inventory.live_sitemap_http = sitemapResponse.status;
  inventory.live_sitemap_urls = liveSitemapUrls.length;
  inventory.live_sitemap_paths = liveSitemapPaths;
  inventory.live_legacy_topic_urls = liveSitemapPaths.filter(
    (route) => route === "/topics" || route.startsWith("/topics/"),
  ).length;
  inventory.live_legacy_label_urls = liveSitemapPaths.filter(
    (route) => route === "/labels" || route.startsWith("/labels/"),
  ).length;
  inventory.live_figure_urls = liveSitemapPaths.filter(
    (route) => route === "/figures" || route.startsWith("/figures/"),
  ).length;
  inventory.live_to_intended_sitemap_gap = inventory.intended_sitemap_urls - inventory.live_sitemap_urls;
  inventory.live_robots_http = robotsResponse.status;
  inventory.live_robots_allows_root = /User-agent:\s*\*[\s\S]*?Allow:\s*\/(?:\s|$)/i.test(liveRobots);
  inventory.live_robots_has_disallow = /^Disallow:/im.test(liveRobots);
  inventory.live_source = {
    http: sourceResponse.status,
    html_bytes: liveSource.length,
    ...inspectHtml("/source", liveSource),
  };
  inventory.live_dashboard = {
    http: dashboardResponse.status,
    html_bytes: liveDashboard.length,
    ...inspectHtml("/dashboard", liveDashboard),
  };
  inventory.live_figures = {
    http: figuresResponse.status,
    html_bytes: liveFigures.length,
    ...inspectHtml("/figures", liveFigures),
  };
}

console.log(JSON.stringify(inventory, null, 2));

if (process.argv.includes("--strict") && inventory.build_crawlability?.failure_count) {
  process.exitCode = 1;
}
