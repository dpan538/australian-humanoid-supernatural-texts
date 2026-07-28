import "server-only";

import { readFile } from "node:fs/promises";
import path from "node:path";
import {
  humanizeArchiveCode,
  labelKey,
  narrativeTypeName,
  recordIdFromRouteSlug,
  sourceIdFromRouteSlug,
  STATE_NAMES,
} from "@/lib/archive-routing";
import type { DateBand, FrontendData, RecordItem, SourceItem } from "@/lib/types";

export const RECORDS_PER_INDEX_PAGE = 100;
export const COLLECTION_RECORD_PREVIEW_LIMIT = 60;
export const LABEL_PAGE_MINIMUM = 4;

export type ArchiveRecordPolicy = {
  pageEligible: boolean;
  indexEligible: boolean;
  reasons: string[];
};

export type ArchiveRecordGroup = {
  key: string;
  label: string;
  records: RecordItem[];
};

export type ArchiveSourceGroup = ArchiveRecordGroup & {
  sourceId: number;
  source: SourceItem | null;
};

export type ArchivePeriodGroup = ArchiveRecordGroup & {
  period: DateBand;
};

type ArchiveCatalogCache = {
  recordsById: Map<number, RecordItem>;
  pageRecords: RecordItem[];
  indexableRecords: RecordItem[];
  indexableNewestFirst: RecordItem[];
  narrativeGroups: ArchiveRecordGroup[];
  labelGroups: ArchiveRecordGroup[];
  sourceGroups: ArchiveSourceGroup[];
  placeGroups: ArchiveRecordGroup[];
  periodGroups: ArchivePeriodGroup[];
  recordsByNarrative: Map<string, RecordItem[]>;
  recordsByLabel: Map<string, RecordItem[]>;
  recordsByState: Map<string, RecordItem[]>;
  recordsBySource: Map<number, RecordItem[]>;
};

const archiveCatalogCaches = new WeakMap<FrontendData, ArchiveCatalogCache>();
let archiveDataPromise: Promise<FrontendData> | null = null;

export function loadArchiveData(): Promise<FrontendData> {
  if (!archiveDataPromise) {
    archiveDataPromise = loadArchiveDataFile();
  }
  return archiveDataPromise;
}

export function archiveRecordPolicy(record: RecordItem): ArchiveRecordPolicy {
  const reasons: string[] = [];
  const includeStatus = record.include_status ?? "";
  const ethicsFlag = record.ethics_flag ?? "";

  if (includeStatus === "control_only" || includeStatus === "exclude_core") {
    reasons.push("control_or_excluded_record");
  }
  if (record.ontology_code === "non_humanoid_control") {
    reasons.push("outside_supernatural_humanoid_scope");
  }
  if (!record.title || !record.url || !record.source_name) {
    reasons.push("missing_public_page_fields");
  }

  const pageEligible = reasons.length === 0;
  const reviewedForIndex =
    ethicsFlag === "ok_public" ||
    ethicsFlag.startsWith("public_");

  if (!reviewedForIndex) {
    reasons.push("search_index_review_required");
  }

  return {
    pageEligible,
    indexEligible: pageEligible && reviewedForIndex,
    reasons,
  };
}

export function publicRecordPages(data: FrontendData) {
  return catalogFor(data).pageRecords;
}

export function indexableRecords(data: FrontendData) {
  return catalogFor(data).indexableRecords;
}

export function recordByRouteSlug(data: FrontendData, slug: string) {
  const recordId = recordIdFromRouteSlug(slug);
  if (recordId === null) {
    return null;
  }
  const record = catalogFor(data).recordsById.get(recordId) ?? null;
  return record && archiveRecordPolicy(record).pageEligible ? record : null;
}

export function recordsIndexPageCount(data: FrontendData) {
  return Math.max(1, Math.ceil(indexableRecords(data).length / RECORDS_PER_INDEX_PAGE));
}

export function recordsForIndexPage(data: FrontendData, page: number) {
  const records = catalogFor(data).indexableNewestFirst;
  const start = (page - 1) * RECORDS_PER_INDEX_PAGE;
  return records.slice(start, start + RECORDS_PER_INDEX_PAGE);
}

export function narrativeTypeGroups(data: FrontendData) {
  return catalogFor(data).narrativeGroups;
}

export function labelGroups(data: FrontendData) {
  return catalogFor(data).labelGroups;
}

export function sourceGroups(data: FrontendData): ArchiveSourceGroup[] {
  return catalogFor(data).sourceGroups;
}

export function sourceGroupByRouteSlug(data: FrontendData, slug: string) {
  const sourceId = sourceIdFromRouteSlug(slug);
  return sourceId === null ? null : sourceGroups(data).find((group) => group.sourceId === sourceId) ?? null;
}

export function placeGroups(data: FrontendData) {
  return catalogFor(data).placeGroups;
}

export function periodGroups(data: FrontendData): ArchivePeriodGroup[] {
  return catalogFor(data).periodGroups;
}

export function relatedRecords(data: FrontendData, record: RecordItem, limit = 6) {
  const catalog = catalogFor(data);
  const figure = labelKey(record.canonical_figure_guess || record.canonical_figure);
  const related: RecordItem[] = [];
  const seen = new Set([record.record_id]);
  appendRelated(related, seen, figure !== "unspecified" ? catalog.recordsByLabel.get(figure) : undefined, limit);
  appendRelated(related, seen, record.ontology_code ? catalog.recordsByNarrative.get(record.ontology_code) : undefined, limit);
  appendRelated(related, seen, record.state_territory ? catalog.recordsByState.get(record.state_territory) : undefined, limit);
  appendRelated(related, seen, catalog.recordsBySource.get(record.source_id), limit);
  return related;
}

export function archiveInventory(data: FrontendData) {
  const pageRecords = publicRecordPages(data);
  const searchableRecords = indexableRecords(data);
  const narrativeTypes = narrativeTypeGroups(data);
  const labels = labelGroups(data);
  const sources = sourceGroups(data);
  const places = placeGroups(data);
  const periods = periodGroups(data);
  const recordIndexPages = recordsIndexPageCount(data);

  return {
    publicDataRecords: data.records.length,
    recordPages: pageRecords.length,
    indexableRecordPages: searchableRecords.length,
    reviewOnlyRecordPages: pageRecords.length - searchableRecords.length,
    recordIndexPages,
    narrativeTypePages: narrativeTypes.length,
    labelPages: labels.length,
    sourcePages: sources.length,
    placePages: places.length,
    periodPages: periods.length,
    generatedAt: data.generated_at,
  };
}

export function collectionPreview(records: RecordItem[]) {
  return records.slice(0, COLLECTION_RECORD_PREVIEW_LIMIT);
}

function groupRecords(
  records: RecordItem[],
  keyFor: (record: RecordItem) => string,
  labelFor: (record: RecordItem) => string,
): ArchiveRecordGroup[] {
  const groups = new Map<string, ArchiveRecordGroup>();
  for (const record of records) {
    const key = keyFor(record);
    const current = groups.get(key);
    if (current) {
      current.records.push(record);
      continue;
    }
    groups.set(key, {
      key,
      label: labelFor(record),
      records: [record],
    });
  }
  return [...groups.values()]
    .map((group) => ({
      ...group,
      records: group.records.sort(compareRecordsNewestFirst),
    }))
    .sort((a, b) => b.records.length - a.records.length || a.label.localeCompare(b.label));
}

async function loadArchiveDataFile(): Promise<FrontendData> {
  const dataPath = path.join(process.cwd(), "public", "data", "frontend-data.json");
  const payload = JSON.parse(await readFile(dataPath, "utf8")) as FrontendData;
  if (!payload.scope?.public_only || !Array.isArray(payload.records)) {
    throw new Error("The public archive export is missing its public-only scope contract.");
  }
  return payload;
}

function catalogFor(data: FrontendData): ArchiveCatalogCache {
  const cached = archiveCatalogCaches.get(data);
  if (cached) {
    return cached;
  }

  const recordsById = new Map(data.records.map((record) => [record.record_id, record]));
  const pageRecords = data.records.filter((record) => archiveRecordPolicy(record).pageEligible);
  const searchable = data.records.filter((record) => archiveRecordPolicy(record).indexEligible);
  const indexableNewestFirst = [...searchable].sort(compareRecordsNewestFirst);
  const sourcesById = new Map(data.sources.map((source) => [source.source_id, source]));
  const narrativeGroups = groupRecords(
    searchable.filter((record) => Boolean(record.ontology_code)),
    (record) => record.ontology_code ?? "unspecified",
    (record) => narrativeTypeName(record.ontology_code ?? "unspecified"),
  );
  const labels = groupRecords(
    searchable.filter((record) => Boolean(record.canonical_figure_guess || record.canonical_figure)),
    (record) => labelKey(record.canonical_figure_guess || record.canonical_figure),
    (record) => record.canonical_figure_guess || record.canonical_figure || "Unspecified",
  )
    .filter((group) => group.records.length >= LABEL_PAGE_MINIMUM)
    .map((group) => ({
      ...group,
      label:
        group.label === group.label.toLowerCase() || group.label.includes("_")
          ? humanizeArchiveCode(group.label)
          : group.label,
    }));
  const sources = groupRecords(
    searchable,
    (record) => String(record.source_id),
    (record) => record.source_name || `Source ${record.source_id}`,
  ).map((group) => ({
    ...group,
    sourceId: Number(group.key),
    source: sourcesById.get(Number(group.key)) ?? null,
  }));
  const places = groupRecords(
    searchable.filter((record) => Boolean(record.state_territory)),
    (record) => record.state_territory ?? "unknown",
    (record) => STATE_NAMES[record.state_territory ?? ""] ?? record.state_territory ?? "Unspecified",
  );
  const periods = data.date_bands
    .map((period) => ({
      key: period.id,
      label: period.label,
      records: searchable.filter((record) => record.date_band === period.id).sort(compareRecordsNewestFirst),
      period,
    }))
    .filter((group) => group.records.length > 0);
  const recordsByNarrative = groupMap(searchable, (record) => record.ontology_code);
  const recordsByLabel = groupMap(searchable, (record) => {
    const key = labelKey(record.canonical_figure_guess || record.canonical_figure);
    return key === "unspecified" ? null : key;
  });
  const recordsByState = groupMap(searchable, (record) => record.state_territory);
  const recordsBySource = groupMap(searchable, (record) => record.source_id);

  const catalog: ArchiveCatalogCache = {
    recordsById,
    pageRecords,
    indexableRecords: searchable,
    indexableNewestFirst,
    narrativeGroups,
    labelGroups: labels,
    sourceGroups: sources,
    placeGroups: places,
    periodGroups: periods,
    recordsByNarrative,
    recordsByLabel,
    recordsByState,
    recordsBySource,
  };
  archiveCatalogCaches.set(data, catalog);
  return catalog;
}

function groupMap<Key extends string | number>(
  records: RecordItem[],
  keyFor: (record: RecordItem) => Key | null | undefined,
) {
  const groups = new Map<Key, RecordItem[]>();
  for (const record of records) {
    const key = keyFor(record);
    if (key === null || key === undefined || key === "") {
      continue;
    }
    const group = groups.get(key) ?? [];
    group.push(record);
    groups.set(key, group);
  }
  return groups;
}

function appendRelated(
  target: RecordItem[],
  seen: Set<number>,
  candidates: RecordItem[] | undefined,
  limit: number,
) {
  for (const candidate of candidates ?? []) {
    if (target.length >= limit) {
      return;
    }
    if (seen.has(candidate.record_id)) {
      continue;
    }
    seen.add(candidate.record_id);
    target.push(candidate);
  }
}

function compareRecordsNewestFirst(a: RecordItem, b: RecordItem) {
  return (b.year ?? -1) - (a.year ?? -1) || b.record_id - a.record_id;
}
