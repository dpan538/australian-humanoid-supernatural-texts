import { figureProfileFor, normalizeFigureLabel } from "@/lib/figure-profiles";
import { buildSourceRegistryData } from "@/lib/source-view-data";
import type { FrontendData, RecordItem } from "@/lib/types";

const MOBILE_STATE_CODES = ["WA", "NT", "SA", "QLD", "NSW", "VIC", "TAS", "ACT"] as const;
export const MOBILE_RECORD_CHUNK_SIZE = 480;

export type MobileArchiveData = {
  schema_version: string;
  generated_from: string;
  generated_at: string;
  summary: {
    recordCount: number;
    mappedRecordCount: number;
    sourceCount: number;
    sourceTypeCount: number;
    earliestYear: number;
    latestYear: number;
    ethicalNote: string;
  };
  map: {
    stateCounts: Array<{ code: string; count: number }>;
    interpretation: string;
  };
  recordArchive: {
    recordCount: number;
    chunkSize: number;
    chunkCount: number;
    version: string;
    baseUrl: string;
  };
  density: {
    periods: MobilePeriod[];
    annualSeries: Array<{ year: number; count: number }>;
  };
  sources: {
    metrics: {
      sourceOrgs: number;
      publicRecords: number;
      sourceTypes: number;
    };
    rollup: Array<{ id: string; label: string; color: string; records: number; orgs: number }>;
    typeRows: Array<{ id: string; label: string; familyLabel: string; color: string; records: number; orgs: number }>;
    registry: Array<{
      id: number;
      name: string;
      sourceType: string;
      displayType: string;
      familyId: string;
      familyLabel: string;
      color: string;
      publicRole: string;
      recordCount: number;
      publicness: string | null;
      baseUrl: string | null;
      ethicsNotes: string | null;
    }>;
  };
  figures: MobileFigureSearchEntry[];
};

export type MobileFigureSearchEntry = {
  name: string;
  slug: string;
  description: string;
  aliases: string[];
  recordCount: number;
  earliestYear: number | null;
  latestYear: number | null;
};

export type MobilePeriod = {
  id: string;
  label: string;
  records: number;
  mapped: number;
  mappedShare: number;
  plannedQueries: number;
  recordShare: number;
  maxShare: number;
};

/**
 * Build the deliberately small payload used by the independent mobile shell.
 * The full public dataset remains available to phones through deferred record
 * chunks; this projection keeps the initial render from parsing and retaining
 * that complete archive on the main thread before the mobile shell is usable.
 */
export function buildMobileArchiveData(data: FrontendData): MobileArchiveData {
  const sourceData = buildSourceRegistryData(data);
  const mappedStateCounts = mobileMappedStateCounts(data);
  const datedYears = data.records
    .map((record) => record.year)
    .filter((year): year is number => typeof year === "number" && Number.isFinite(year));
  const recordCount = data.summary.record_count || data.records.length;
  const mappedRecordCount =
    data.summary.mapped_record_count ||
    Object.values(mappedStateCounts).reduce((total, count) => total + count, 0);
  const maxPeriodRecords = Math.max(1, ...data.date_bands.map((period) => period.record_count || 0));

  return {
    schema_version: "mobile-archive/v2",
    generated_from: data.schema_version,
    generated_at: data.generated_at,
    summary: {
      recordCount,
      mappedRecordCount,
      sourceCount: sourceData.metrics.sourceOrgs,
      sourceTypeCount: sourceData.metrics.sourceTypes,
      earliestYear: data.summary.earliest_year ?? (datedYears.length ? Math.min(...datedYears) : 0),
      latestYear: data.summary.latest_year ?? (datedYears.length ? Math.max(...datedYears) : 0),
      ethicalNote: data.scope.ethical_note,
    },
    map: {
      stateCounts: MOBILE_STATE_CODES.map((code) => ({ code, count: mappedStateCounts[code] ?? 0 })),
      interpretation: "Markers are public display locations for records, not proof, habitats, or populations.",
    },
    recordArchive: {
      recordCount,
      chunkSize: MOBILE_RECORD_CHUNK_SIZE,
      chunkCount: Math.ceil(data.records.length / MOBILE_RECORD_CHUNK_SIZE),
      version: `${data.generated_at.replace(/[^0-9A-Za-z]/g, "").slice(0, 32)}-${recordCount}`,
      baseUrl: "/data/mobile-records",
    },
    density: {
      periods: data.date_bands.map((period) => {
        const records = period.record_count || 0;
        const mapped = period.mapped_count || 0;
        return {
          id: period.id,
          label: period.short_label || period.label,
          records,
          mapped,
          mappedShare: records ? mapped / records : 0,
          plannedQueries: period.planned_query_count || 0,
          recordShare: recordCount ? records / recordCount : 0,
          maxShare: records / maxPeriodRecords,
        };
      }),
      annualSeries: buildMobileAnnualSeries(data),
    },
    sources: {
      metrics: sourceData.metrics,
      rollup: sourceData.rollupRows.map((row) => ({
        id: row.id,
        label: row.label,
        color: row.color,
        records: row.records,
        orgs: row.orgs,
      })),
      typeRows: sourceData.typeRows.map((row) => ({
        id: row.id,
        label: row.label,
        familyLabel: row.familyLabel,
        color: row.color,
        records: row.records,
        orgs: row.orgs,
      })),
      registry: sourceData.registryRows.map((row) => ({
        id: row.source.source_id,
        name: row.source.source_name,
        sourceType: row.source.source_type,
        displayType: row.displayType,
        familyId: row.familyId,
        familyLabel: row.familyLabel,
        color: row.color,
        publicRole: row.publicRole,
        recordCount: row.recordCount,
        publicness: row.source.publicness_level,
        baseUrl: row.source.base_url,
        ethicsNotes: row.source.ethics_notes,
      })),
    },
    figures: buildMobileFigureSearchEntries(data),
  };
}

function mobileMappedStateCounts(data: FrontendData) {
  if (data.summary.mapped_state_counts) {
    return data.summary.mapped_state_counts;
  }

  return (data.map_flags ?? []).reduce<Record<string, number>>((counts, flag) => {
    const code = flag.state_territory;
    if (code) {
      counts[code] = (counts[code] ?? 0) + 1;
    }
    return counts;
  }, {});
}

function buildMobileFigureSearchEntries(data: FrontendData): MobileFigureSearchEntry[] {
  const groups = new Map<
    string,
    {
      name: string;
      description: string;
      aliases: Set<string>;
      recordCount: number;
      years: number[];
    }
  >();

  for (const record of data.records) {
    if (!mobileRecordSearchEligible(record)) {
      continue;
    }
    const printedLabel = (record.canonical_figure_guess || record.canonical_figure || "").trim();
    if (!printedLabel) {
      continue;
    }
    const profile = figureProfileFor(printedLabel);
    const group = groups.get(profile.slug) ?? {
      name: profile.label,
      description: profile.shortDescription,
      aliases: new Set(profile.aliases ?? []),
      recordCount: 0,
      years: [],
    };
    group.recordCount += 1;
    group.aliases.add(printedLabel);
    if (typeof record.year === "number" && Number.isFinite(record.year)) {
      group.years.push(record.year);
    }
    groups.set(profile.slug, group);
  }

  for (const figure of data.figures) {
    if (
      figure.include_status === "control_only" ||
      figure.include_status === "exclude_core" ||
      figure.humanoid_degree === "non_humanoid"
    ) {
      continue;
    }
    const profile = figureProfileFor(figure.canonical_name);
    const group = groups.get(profile.slug) ?? {
      name: profile.label,
      description: profile.shortDescription,
      aliases: new Set(profile.aliases ?? []),
      recordCount: 0,
      years: [],
    };
    group.aliases.add(figure.canonical_name);
    for (const alias of figure.aliases ?? []) {
      group.aliases.add(alias.alias);
    }
    groups.set(profile.slug, group);
  }

  return [...groups.entries()]
    .map(([slug, group]) => ({
      name: group.name,
      slug,
      description: group.description,
      aliases: [...group.aliases]
        .filter((alias) => normalizeFigureLabel(alias) !== normalizeFigureLabel(group.name))
        .sort((left, right) => left.localeCompare(right)),
      recordCount: group.recordCount,
      earliestYear: group.years.length ? Math.min(...group.years) : null,
      latestYear: group.years.length ? Math.max(...group.years) : null,
    }))
    .filter((entry) => entry.recordCount > 0)
    .sort((left, right) => right.recordCount - left.recordCount || left.name.localeCompare(right.name));
}

function mobileRecordSearchEligible(record: RecordItem) {
  const includeStatus = record.include_status ?? "";
  const ethicsFlag = record.ethics_flag ?? "";
  return (
    includeStatus !== "control_only" &&
    includeStatus !== "exclude_core" &&
    record.ontology_code !== "non_humanoid_control" &&
    Boolean(record.title && record.url && record.source_name) &&
    (ethicsFlag === "ok_public" || ethicsFlag.startsWith("public_"))
  );
}

function buildMobileAnnualSeries(data: FrontendData) {
  const fromSummary = Object.entries(data.summary.records_by_year || {})
    .map(([year, count]) => ({ year: Number(year), count: Number(count) }))
    .filter((row) => Number.isFinite(row.year) && Number.isFinite(row.count))
    .sort((left, right) => left.year - right.year);

  if (fromSummary.length) {
    return fromSummary;
  }

  const counts = new Map<number, number>();
  for (const record of data.records) {
    if (typeof record.year !== "number" || !Number.isFinite(record.year)) {
      continue;
    }
    counts.set(record.year, (counts.get(record.year) ?? 0) + 1);
  }
  return [...counts.entries()].sort((left, right) => left[0] - right[0]).map(([year, count]) => ({ year, count }));
}
