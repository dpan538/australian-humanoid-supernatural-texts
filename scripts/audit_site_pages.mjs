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

const recordIndexPages = Math.max(1, Math.ceil(indexRecords.length / 100));
const narrativeTypePages = groupCount(indexRecords, (record) => record.ontology_code);
const labelPages = [...groupedCounts(indexRecords, labelKey).values()].filter((count) => count >= 4).length;
const sourceCounts = groupedCounts(indexRecords, (record) => record.source_id);
const sourcePages = sourceCounts.size;
const indexedSourcePages = [...sourceCounts.values()].filter((count) => count >= 2).length;
const placePages = groupCount(indexRecords, (record) => record.state_territory);
const periodPages = data.date_bands.filter((period) =>
  indexRecords.some((record) => record.date_band === period.id),
).length;
const staticIndexPaths = 14;
const topicDetailPages = 6;

const inventory = {
  data_generated_at: data.generated_at,
  public_data_records: data.records.length,
  record_pages: pageRecords.length,
  indexable_record_pages: indexRecords.length,
  review_only_record_pages: pageRecords.length - indexRecords.length,
  record_index_pages: recordIndexPages,
  narrative_type_pages: narrativeTypePages,
  label_pages: labelPages,
  source_pages: sourcePages,
  indexed_source_pages: indexedSourcePages,
  place_pages: placePages,
  period_pages: periodPages,
  intended_content_pages:
    staticIndexPaths +
    topicDetailPages +
    pageRecords.length +
    Math.max(0, recordIndexPages - 1) +
    narrativeTypePages +
    labelPages +
    sourcePages +
    placePages +
    periodPages,
  intended_sitemap_urls:
    staticIndexPaths +
    topicDetailPages +
    Math.max(0, recordIndexPages - 1) +
    narrativeTypePages +
    labelPages +
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
  const description = decodeText(
    textMatch(html, /<meta[^>]+name=["']description["'][^>]+content=["']([^"']*)["'][^>]*>/i),
  );
  const canonical = textMatch(html, /<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["'][^>]*>/i);
  const robots = textMatch(html, /<meta[^>]+name=["']robots["'][^>]+content=["']([^"']+)["'][^>]*>/i);
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
    hasStructuredData: /type=["']application\/ld\+json["']/i.test(html),
    visibleTextLength: visibleText.length,
  };
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
  const sitemapUrls = [...sitemapXml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => decodeText(match[1]));
  const sitemapPaths = new Set(sitemapUrls.map((url) => new URL(url).pathname.replace(/\/$/, "") || "/"));
  const pageByRoute = new Map(contentPages.map((page) => [page.route, page]));
  const sitemapMissingHtml = [...sitemapPaths].filter((route) => !pageByRoute.has(route));
  const indexablePages = contentPages.filter((page) => !page.noindex && page.route !== "/map");
  const indexableMissingSitemap = indexablePages
    .filter((page) => !sitemapPaths.has(page.route))
    .map((page) => page.route);
  const sitemapNoindexPages = [...sitemapPaths]
    .filter((route) => pageByRoute.get(route)?.noindex);
  const canonicalTargets = contentPages
    .map((page) => page.canonical)
    .filter(Boolean)
    .map((url) => new URL(url).pathname.replace(/\/$/, "") || "/");
  const missingCanonicalTargets = canonicalTargets.filter((route) => !pageByRoute.has(route));
  const failures = {
    missing_title: contentPages.filter((page) => !page.title).map((page) => page.route),
    missing_description: contentPages.filter((page) => !page.description).map((page) => page.route),
    missing_canonical: contentPages.filter((page) => !page.canonical).map((page) => page.route),
    missing_robots_meta: contentPages.filter((page) => !page.robots).map((page) => page.route),
    missing_h1: contentPages.filter((page) => !page.hasH1).map((page) => page.route),
    thin_server_html: contentPages.filter((page) => page.visibleTextLength < 120).map((page) => page.route),
    sitemap_missing_html: sitemapMissingHtml,
    indexable_missing_sitemap: indexableMissingSitemap,
    sitemap_contains_noindex: sitemapNoindexPages,
    missing_canonical_targets: [...new Set(missingCanonicalTargets)],
  };
  const failureCount = Object.values(failures).reduce((total, routes) => total + routes.length, 0);
  return {
    generated_html_pages: pages.length,
    content_html_pages: contentPages.length,
    indexable_html_pages: indexablePages.length,
    crawlable_noindex_pages: contentPages.filter((page) => page.noindex).length,
    pages_with_structured_data: contentPages.filter((page) => page.hasStructuredData).length,
    sitemap_urls: sitemapUrls.length,
    sitemap_unique_urls: new Set(sitemapUrls).size,
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
  const [sitemapResponse, robotsResponse, sourceResponse, dashboardResponse] = await Promise.all([
    fetch("https://ausfigures.com/sitemap.xml"),
    fetch("https://ausfigures.com/robots.txt"),
    fetch("https://ausfigures.com/source"),
    fetch("https://ausfigures.com/dashboard"),
  ]);
  const [xml, liveRobots, liveSource, liveDashboard] = await Promise.all([
    sitemapResponse.text(),
    robotsResponse.text(),
    sourceResponse.text(),
    dashboardResponse.text(),
  ]);
  const liveSitemapUrls = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => decodeText(match[1]));
  inventory.live_sitemap_http = sitemapResponse.status;
  inventory.live_sitemap_urls = liveSitemapUrls.length;
  inventory.live_sitemap_paths = liveSitemapUrls.map((url) => new URL(url).pathname);
  inventory.live_to_intended_sitemap_gap = inventory.intended_sitemap_urls - inventory.live_sitemap_urls;
  inventory.live_robots_http = robotsResponse.status;
  inventory.live_robots_allows_root = /User-agent:\s*\*[\s\S]*?Allow:\s*\/(?:\s|$)/i.test(liveRobots);
  inventory.live_robots_has_disallow = /^Disallow:/im.test(liveRobots);
  inventory.live_source = {
    http: sourceResponse.status,
    html_bytes: liveSource.length,
    has_title: /<title[^>]*>[\s\S]*?<\/title>/i.test(liveSource),
    has_description: /<meta[^>]+name=["']description["']/i.test(liveSource),
    has_canonical: /<link[^>]+rel=["']canonical["']/i.test(liveSource),
    has_structured_data: /type=["']application\/ld\+json["']/i.test(liveSource),
  };
  inventory.live_dashboard = {
    http: dashboardResponse.status,
    html_bytes: liveDashboard.length,
    has_title: /<title[^>]*>[\s\S]*?<\/title>/i.test(liveDashboard),
    has_description: /<meta[^>]+name=["']description["']/i.test(liveDashboard),
    has_canonical: /<link[^>]+rel=["']canonical["']/i.test(liveDashboard),
    has_structured_data: /type=["']application\/ld\+json["']/i.test(liveDashboard),
  };
}

console.log(JSON.stringify(inventory, null, 2));

if (process.argv.includes("--strict") && inventory.build_crawlability?.failure_count) {
  process.exitCode = 1;
}
