import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const projectRoot = process.cwd();
const strict = process.argv.includes("--strict");
const auditBuild = process.argv.includes("--build");
const auditDate = new Date().toISOString();
const releaseDate = auditDate.slice(0, 10);
const dataPath = path.join(projectRoot, "public", "data", "frontend-data.json");
const data = JSON.parse(await readFile(dataPath, "utf8"));

const blockers = [];
const disclosures = [];
const checks = [];

const addCheck = (id, label, passed, detail) => {
  checks.push({ id, label, passed, detail });
  if (!passed) blockers.push({ id, detail });
};
const addDisclosure = (id, label, detail, count = null) => {
  disclosures.push({ id, label, detail, count });
};
const countsBy = (rows, keyFor) => {
  const result = new Map();
  for (const row of rows) {
    const key = keyFor(row);
    if (key === null || key === undefined || key === "") continue;
    result.set(key, (result.get(key) || 0) + 1);
  }
  return result;
};
const duplicates = (rows, keyFor) => {
  const counts = countsBy(rows, keyFor);
  return [...counts.entries()].filter(([, count]) => count > 1);
};
const validHttpUrl = (value) => {
  try {
    const parsed = new URL(value);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      !["localhost", "127.0.0.1", "::1"].includes(parsed.hostname);
  } catch {
    return false;
  }
};
const pageEligible = (record) =>
  record.include_status !== "control_only" &&
  record.include_status !== "exclude_core" &&
  record.ontology_code !== "non_humanoid_control" &&
  Boolean(record.title && record.url && record.source_name);
const indexEligible = (record) =>
  pageEligible(record) &&
  (record.ethics_flag === "ok_public" || String(record.ethics_flag || "").startsWith("public_"));
const archiveSlug = (value, fallback = "record") => {
  const slug = String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-")
    .slice(0, 84)
    .replace(/-+$/g, "");
  return slug || fallback;
};
const recordRoute = (record) => `/records/${record.record_id}-${archiveSlug(record.title, "public-text-record")}`;
const routeHtmlPath = (route) => path.join(projectRoot, ".next", "server", "app", `${route.slice(1)}.html`);
const sortCounts = (map) => [...map.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
const formatNumber = (value) => Number(value || 0).toLocaleString("en-AU");
const percent = (value, total) => total ? `${(100 * value / total).toFixed(2)}%` : "0.00%";

const records = data.records || [];
const sources = data.sources || [];
const queries = data.queries || [];
const mapPoints = data.map_points || [];
const mapFlags = data.map_flags || [];
const recordsBySource = countsBy(records, (record) => record.source_id);
const queriesBySource = countsBy(queries, (query) => query.source_id);
const sourceById = new Map(sources.map((source) => [source.source_id, source]));
const recordById = new Map(records.map((record) => [record.record_id, record]));
const recordIdDuplicates = duplicates(records, (record) => record.record_id);
const sourceIdDuplicates = duplicates(sources, (source) => source.source_id);
const brokenSourceLinks = records.filter((record) => !sourceById.has(record.source_id));
const sourceIdentityMismatches = records.filter((record) => {
  const source = sourceById.get(record.source_id);
  return source && (source.source_name !== record.source_name || source.source_type !== record.source_type);
});
const incompleteRecords = records.filter((record) =>
  !record.record_id ||
  !record.source_id ||
  !record.title ||
  !record.url ||
  !record.source_name ||
  !record.source_type ||
  !record.publicness_level ||
  !record.ethics_flag ||
  !record.ontology_code ||
  (!record.year && !record.date_band)
);
const invalidRecordUrls = records.filter((record) => !validHttpUrl(record.url));
const invalidSourceUrls = sources.filter((source) => source.base_url && !validHttpUrl(source.base_url));
const incompleteSources = sources.filter((source) =>
  !source.source_id ||
  !source.source_name ||
  !source.source_type ||
  !source.access_method ||
  !source.publicness_level ||
  !source.ethics_notes
);
const prohibitedRecords = records.filter((record) =>
  /restricted|suppressed|rejected/i.test(`${record.publicness_level} ${record.publicness_code} ${record.ingestion_status}`) ||
  record.include_status === "exclude_core"
);
const pageRecords = records.filter(pageEligible);
const indexRecords = records.filter(indexEligible);
const reviewOnlyRecords = pageRecords.filter((record) => !indexEligible(record));
const pendingHumanReview = records.filter((record) =>
  record.ethics_flag === "needs_human_review_before_production_import" ||
  record.ethics_flag === "needs_human_ethics_review"
);
const cautionRecords = records.filter((record) => String(record.ethics_flag || "").startsWith("caution_"));
const missingAuthors = records.filter((record) => !String(record.author || "").trim());
const duplicateUrlGroups = duplicates(records, (record) => record.url);
const duplicateUrlOccurrences = duplicateUrlGroups.reduce((total, [, count]) => total + count, 0);
const sourcesWithoutBaseUrl = sources.filter((source) => !source.base_url);
const unusedSources = sources.filter((source) => !recordsBySource.has(source.source_id));

addCheck(
  "summary_record_count",
  "Published record count equals the data array",
  data.summary?.record_count === records.length,
  `summary=${data.summary?.record_count}; records=${records.length}`,
);
addCheck(
  "summary_source_count",
  "Registered source count equals the source array",
  data.summary?.source_count === sources.length,
  `summary=${data.summary?.source_count}; sources=${sources.length}`,
);
addCheck(
  "summary_map_count",
  "Mapped count, map points, and map flags remain one coherent layer",
  data.summary?.mapped_record_count === mapPoints.length &&
    data.summary?.map_flag_count === mapFlags.length &&
    mapPoints.length === mapFlags.length,
  `summary_mapped=${data.summary?.mapped_record_count}; points=${mapPoints.length}; flags=${mapFlags.length}`,
);
addCheck("unique_record_ids", "Every record identifier is unique", recordIdDuplicates.length === 0, `${recordIdDuplicates.length} duplicated identifiers`);
addCheck("unique_source_ids", "Every source identifier is unique", sourceIdDuplicates.length === 0, `${sourceIdDuplicates.length} duplicated identifiers`);
addCheck("source_resolution", "Every record resolves to a registered source", brokenSourceLinks.length === 0, `${brokenSourceLinks.length} broken links`);
addCheck("source_identity", "Record source names and types match the registry", sourceIdentityMismatches.length === 0, `${sourceIdentityMismatches.length} mismatches`);
addCheck("record_minimum_fields", "Every record has the minimum provenance and classification fields", incompleteRecords.length === 0, `${incompleteRecords.length} incomplete records`);
addCheck("record_public_urls", "Every record has a public HTTP(S) source URL", invalidRecordUrls.length === 0, `${invalidRecordUrls.length} invalid or local URLs`);
addCheck("source_minimum_fields", "Every registered source has method, publicness, and ethics metadata", incompleteSources.length === 0, `${incompleteSources.length} incomplete sources`);
addCheck("source_base_urls", "All declared source base URLs are public HTTP(S) URLs", invalidSourceUrls.length === 0, `${invalidSourceUrls.length} invalid source URLs`);
addCheck("public_release_boundary", "Restricted, suppressed, rejected, and explicitly excluded rows are absent from the public record layer", prohibitedRecords.length === 0, `${prohibitedRecords.length} prohibited rows`);

const flagRecordIds = mapFlags.map((flag) => flag.record_id);
const pointRecordIds = mapPoints.map((point) => point.record_id);
const duplicateFlagIds = duplicates(mapFlags, (flag) => flag.record_id);
const orphanFlags = mapFlags.filter((flag) => !recordById.has(flag.record_id));
const orphanPoints = mapPoints.filter((point) => !recordById.has(point.record_id));
const pointSet = new Set(pointRecordIds);
const flagSet = new Set(flagRecordIds);
const strictMappedSet = new Set(records.filter((record) => record.has_strict_map_point).map((record) => record.record_id));
const mapSetMismatch = new Set([
  ...[...pointSet].filter((id) => !flagSet.has(id) || !strictMappedSet.has(id)),
  ...[...flagSet].filter((id) => !pointSet.has(id) || !strictMappedSet.has(id)),
  ...[...strictMappedSet].filter((id) => !pointSet.has(id) || !flagSet.has(id)),
]);
addCheck("unique_map_flags", "Each mapped record produces one display flag", duplicateFlagIds.length === 0, `${duplicateFlagIds.length} duplicated mapped record identifiers`);
addCheck("mapped_record_resolution", "Every map point and flag resolves to a public data record", orphanFlags.length === 0 && orphanPoints.length === 0, `${orphanFlags.length} orphan flags; ${orphanPoints.length} orphan points`);
addCheck("mapped_layer_equivalence", "Strict map points, map points, and display flags contain the same record identifiers", mapSetMismatch.size === 0, `${mapSetMismatch.size} identifier mismatches`);

const sourceConcentration = sortCounts(recordsBySource).map(([sourceId, count]) => ({
  source_id: Number(sourceId),
  source_name: sourceById.get(Number(sourceId))?.source_name || "Unresolved source",
  record_count: count,
  share: Number((100 * count / records.length).toFixed(4)),
}));
const ethicsCounts = sortCounts(countsBy(records, (record) => record.ethics_flag));

addDisclosure(
  "review_only_noindex",
  "Review-only records remain crawlable for inspection but excluded from search indexing",
  `${reviewOnlyRecords.length} pages use noindex; ${pendingHumanReview.length} explicitly await human review and ${cautionRecords.length} carry caution flags.`,
  reviewOnlyRecords.length,
);
addDisclosure(
  "missing_authors",
  "Missing author metadata",
  `${missingAuthors.length} records lack a named author and must be cited by title/source rather than supplied with an invented attribution.`,
  missingAuthors.length,
);
addDisclosure(
  "shared_source_urls",
  "Shared source URLs",
  `${duplicateUrlGroups.length} source URLs support ${duplicateUrlOccurrences} records. This is expected for books, indexes, and multi-record archive pages; record identity must not be inferred from URL uniqueness.`,
  duplicateUrlGroups.length,
);
addDisclosure(
  "source_concentration",
  "Source concentration",
  sourceConcentration.slice(0, 5).map((row) => `${row.source_name}: ${formatNumber(row.record_count)} (${row.share.toFixed(2)}%)`).join("; "),
  sourceConcentration[0]?.record_count || 0,
);
addDisclosure(
  "source_registry_scope",
  "Registered discovery sources versus record-bearing sources",
  `${sources.length - unusedSources.length} of ${sources.length} registered sources currently contribute records; ${unusedSources.length} are query/discovery or reserved registry entries.`,
  unusedSources.length,
);
addDisclosure(
  "generic_source_endpoints",
  "Sources without one fixed base endpoint",
  `${sourcesWithoutBaseUrl.length} registry entries omit base_url; their records still carry direct public URLs and are checked individually.`,
  sourcesWithoutBaseUrl.length,
);

let buildEvidence = null;
if (auditBuild) {
  const buildRoot = path.join(projectRoot, ".next", "server", "app");
  const sitemapPath = path.join(buildRoot, "sitemap.xml.body");
  await access(sitemapPath);
  const sitemapXml = await readFile(sitemapPath, "utf8");
  const sitemapPaths = new Set(
    [...sitemapXml.matchAll(/<loc>([^<]+)<\/loc>/g)]
      .map((match) => new URL(match[1]).pathname.replace(/\/$/, "") || "/"),
  );
  const missingRecordPages = [];
  const missingIndexRoutes = [];
  const reviewRoutesInSitemap = [];
  const reviewRoutesWithoutNoindex = [];
  const indexRoutesWithNoindex = [];
  const recordPagesWithoutOriginalSource = [];

  for (const record of pageRecords) {
    const route = recordRoute(record);
    const htmlPath = routeHtmlPath(route);
    let html = "";
    try {
      html = await readFile(htmlPath, "utf8");
    } catch {
      missingRecordPages.push(route);
      continue;
    }
    const noindex = /<meta[^>]+name=["']robots["'][^>]+content=["'][^"']*\bnoindex\b/i.test(html) ||
      /<meta[^>]+content=["'][^"']*\bnoindex\b[^"']*["'][^>]+name=["']robots["']/i.test(html);
    if (indexEligible(record)) {
      if (!sitemapPaths.has(route)) missingIndexRoutes.push(route);
      if (noindex) indexRoutesWithNoindex.push(route);
    } else {
      if (sitemapPaths.has(route)) reviewRoutesInSitemap.push(route);
      if (!noindex) reviewRoutesWithoutNoindex.push(route);
    }
    const escapedUrl = record.url.replaceAll("&", "\\u0026");
    if (!html.includes(record.url) && !html.includes(escapedUrl)) {
      recordPagesWithoutOriginalSource.push(route);
    }
  }

  const excludedRoutesPublished = records
    .filter((record) => !pageEligible(record))
    .map(recordRoute)
    .filter((route) => sitemapPaths.has(route));

  addCheck("build_record_pages", "Every page-eligible record has a generated HTML page", missingRecordPages.length === 0, `${missingRecordPages.length} missing record pages`);
  addCheck("build_index_sitemap", "Every index-eligible record is present in the sitemap", missingIndexRoutes.length === 0, `${missingIndexRoutes.length} missing sitemap routes`);
  addCheck("build_review_sitemap", "Review-only record pages are absent from the sitemap", reviewRoutesInSitemap.length === 0, `${reviewRoutesInSitemap.length} review routes in sitemap`);
  addCheck("build_review_noindex", "Every review-only record page declares noindex", reviewRoutesWithoutNoindex.length === 0, `${reviewRoutesWithoutNoindex.length} review pages missing noindex`);
  addCheck("build_index_robots", "Index-eligible record pages do not declare noindex", indexRoutesWithNoindex.length === 0, `${indexRoutesWithNoindex.length} index pages with noindex`);
  addCheck("build_source_citation", "Every generated record page retains its original public source URL", recordPagesWithoutOriginalSource.length === 0, `${recordPagesWithoutOriginalSource.length} pages without the source URL`);
  addCheck("build_excluded_routes", "Control and excluded records are absent from the sitemap", excludedRoutesPublished.length === 0, `${excludedRoutesPublished.length} excluded routes in sitemap`);

  buildEvidence = {
    sitemap_url_count: sitemapPaths.size,
    generated_record_pages_checked: pageRecords.length,
    indexable_record_pages_checked: indexRecords.length,
    review_only_record_pages_checked: reviewOnlyRecords.length,
  };
}

const sourceAudit = sources
  .map((source) => ({
    source_id: source.source_id,
    source_name: source.source_name,
    source_type: source.source_type,
    record_count: recordsBySource.get(source.source_id) || 0,
    query_count: queriesBySource.get(source.source_id) || 0,
    base_url_status: source.base_url ? "declared" : "record-level URLs",
    access_method: source.access_method,
    publicness_level: source.publicness_level,
    metadata_complete: !incompleteSources.includes(source) && !invalidSourceUrls.includes(source),
  }))
  .sort((a, b) => b.record_count - a.record_count || a.source_id - b.source_id);

const result = {
  schema_version: "academic-rigour-audit/v1",
  audited_at: auditDate,
  release_date: releaseDate,
  data_generated_at: data.generated_at,
  strict,
  build_audited: auditBuild,
  scope: {
    records_audited: records.length,
    sources_audited: sources.length,
    queries_cross_checked: queries.length,
    map_points_audited: mapPoints.length,
    map_flags_audited: mapFlags.length,
    audited_record_ids: records.map((record) => record.record_id),
  },
  publication_policy: {
    page_eligible: pageRecords.length,
    index_eligible: indexRecords.length,
    review_only_noindex: reviewOnlyRecords.length,
    pending_human_review: pendingHumanReview.length,
    caution_flagged: cautionRecords.length,
  },
  checks,
  blockers,
  disclosures,
  source_concentration: sourceConcentration,
  ethics_distribution: Object.fromEntries(ethicsCounts),
  source_audit: sourceAudit,
  build_evidence: buildEvidence,
};

const reportDirectory = path.join(projectRoot, "docs", "release");
const dataReportDirectory = path.join(projectRoot, "data", "processed", "v2");
await mkdir(reportDirectory, { recursive: true });
await mkdir(dataReportDirectory, { recursive: true });

const jsonReportPath = path.join(dataReportDirectory, `academic_rigour_audit_${releaseDate}.json`);
const markdownReportPath = path.join(reportDirectory, `ACADEMIC_RIGOUR_AUDIT_${releaseDate}.md`);
await writeFile(jsonReportPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");

const checkRows = checks
  .map((check) => `| ${check.passed ? "PASS" : "FAIL"} | ${check.label} | ${String(check.detail).replaceAll("|", "\\|")} |`)
  .join("\n");
const disclosureRows = disclosures
  .map((item) => `| ${item.label} | ${String(item.detail).replaceAll("|", "\\|")} |`)
  .join("\n");
const sourceRows = sourceAudit
  .map((source) => `| ${source.source_id} | ${source.source_name.replaceAll("|", "\\|")} | ${source.source_type} | ${formatNumber(source.record_count)} | ${formatNumber(source.query_count)} | ${source.base_url_status} | ${source.metadata_complete ? "PASS" : "FAIL"} |`)
  .join("\n");
const ethicsRows = ethicsCounts
  .map(([flag, count]) => `| ${flag} | ${formatNumber(count)} | ${percent(count, records.length)} |`)
  .join("\n");

const markdown = `# Academic Rigour Audit — ${releaseDate}

## Decision

**${blockers.length === 0 ? "PASS — eligible for release" : `FAIL — ${blockers.length} blocking issue(s)`}**

This audit covers every public data record, every registered source, the record-to-source relationships, ethics/indexing policy, mapped-record equivalence, and${auditBuild ? " the generated production build" : " (without build-output validation)"}. It evaluates provenance and publication controls; it does not validate the truth of supernatural claims.

## Scope

- Data export generated: \`${data.generated_at}\`
- Records audited: **${formatNumber(records.length)}**
- Registered sources audited: **${formatNumber(sources.length)}**
- Discovery queries cross-checked: **${formatNumber(queries.length)}**
- Map points / display flags audited: **${formatNumber(mapPoints.length)} / ${formatNumber(mapFlags.length)}**
- Page-eligible / index-eligible / review-only pages: **${formatNumber(pageRecords.length)} / ${formatNumber(indexRecords.length)} / ${formatNumber(reviewOnlyRecords.length)}**

## Release checks

| Result | Check | Evidence |
|---|---|---|
${checkRows}

## Required scholarly disclosures

| Disclosure | Current evidence |
|---|---|
${disclosureRows}

Missing authors are not inferred. Shared URLs are not deduplicated automatically because a book, archive index, or source page may support several separately coded public records. Source concentration and incomplete mapping are properties of the archive corpus, not estimates of real-world incidence.

## Ethics and review distribution

| Ethics flag | Records | Corpus share |
|---|---:|---:|
${ethicsRows}

Only \`ok_public\` and \`public_*\` records are search-index eligible. Caution and pending-review records remain inspectable as source-grounded archive rows but are excluded from the sitemap and carry \`noindex\`.

## Complete source-register audit

| ID | Source | Type | Records | Queries | Endpoint basis | Metadata |
|---:|---|---|---:|---:|---|---|
${sourceRows}

## Citation rule

Cite AusFigures for the aggregation, coding, interface, and public export. For a claim about one record, also cite the original public source linked on that record page. Do not cite AusFigures as evidence that a reported supernatural event occurred.

## Machine-readable evidence

The complete audit, all audited record identifiers, source-register results, source concentration, ethics distribution, build evidence, disclosures, and blocker list are stored in:

\`data/processed/v2/academic_rigour_audit_${releaseDate}.json\`
`;
await writeFile(markdownReportPath, markdown, "utf8");

console.log(JSON.stringify({
  decision: blockers.length === 0 ? "PASS" : "FAIL",
  blockers: blockers.length,
  checks: checks.length,
  records_audited: records.length,
  sources_audited: sources.length,
  page_eligible: pageRecords.length,
  index_eligible: indexRecords.length,
  review_only_noindex: reviewOnlyRecords.length,
  reports: [
    path.relative(projectRoot, markdownReportPath),
    path.relative(projectRoot, jsonReportPath),
  ],
}, null, 2));

if (strict && blockers.length > 0) {
  process.exitCode = 1;
}
