import "server-only";

import {
  encyclopediaFigureGroups,
  relatedEncyclopediaFigures,
} from "@/lib/archive-catalog";
import {
  figurePath,
  humanizeArchiveCode,
  narrativeTypeName,
  narrativeTypePath,
  periodPath,
  placePath,
  recordPath,
  sourcePath,
  STATE_NAMES,
} from "@/lib/archive-routing";
import type {
  FigureDictionaryEntry,
  FigureDictionaryFrequency,
  FigureDictionaryLink,
} from "@/lib/figure-dictionary-types";
import type { FrontendData } from "@/lib/types";

const RECORD_PREVIEW_LIMIT = 6;
const RELATED_PREVIEW_LIMIT = 4;

export function buildFigureDictionaryEntries(data: FrontendData): FigureDictionaryEntry[] {
  return encyclopediaFigureGroups(data).map((group, index) => {
    const records = group.records;
    const years = records
      .map((record) => record.year)
      .filter((year): year is number => typeof year === "number" && Number.isFinite(year));
    const narratives = uniqueLinks(
      records
        .filter((record) => record.ontology_code)
        .map((record) => ({
          href: narrativeTypePath(record.ontology_code as string),
          label: narrativeTypeName(record.ontology_code as string),
        })),
    );
    const places = uniqueLinks(
      records
        .filter((record) => record.state_territory)
        .map((record) => ({
          href: placePath(record.state_territory as string),
          label: STATE_NAMES[record.state_territory as string] ?? (record.state_territory as string),
        })),
    );
    const sources = uniqueLinks(
      records
        .filter((record) => record.source_name)
        .map((record) => ({
          href: sourcePath(record.source_id, record.source_name as string),
          label: record.source_name as string,
        })),
    );
    const periods = uniqueLinks(
      records
        .filter((record) => record.date_band)
        .map((record) => ({
          href: periodPath(record.date_band),
          label: humanizeArchiveCode(record.date_band),
      })),
    );
    const nameFrequency = frequencyRows(
      records.map((record) => ({
        key: cleanFrequencyLabel(
          record.figure_name_as_printed ||
          record.canonical_figure ||
          group.label,
        ),
        href: null,
      })),
      8,
    );
    const regionFrequency = frequencyRows(
      records
        .filter((record) => record.state_territory)
        .map((record) => ({
          key: STATE_NAMES[record.state_territory as string] ?? (record.state_territory as string),
          href: placePath(record.state_territory as string),
        })),
      8,
    );
    const periodFrequency = frequencyRows(
      records
        .filter((record) => record.date_band)
        .map((record) => ({
          key: humanizeArchiveCode(record.date_band),
          href: periodPath(record.date_band),
        })),
      8,
    );
    const sourceFrequency = frequencyRows(
      records
        .filter((record) => record.source_name)
        .map((record) => ({
          key: record.source_name as string,
          href: sourcePath(record.source_id, record.source_name as string),
        })),
      6,
    );
    const narrativeFrequency = frequencyRows(
      records
        .filter((record) => record.ontology_code || record.genre)
        .map((record) => {
          const code = record.ontology_code || record.genre || "unspecified";
          return {
            key: narrativeTypeName(code),
            href: record.ontology_code ? narrativeTypePath(record.ontology_code) : null,
          };
        }),
      6,
    );
    const narrativeCodes = frequencyCodeRows(records);
    const timeline = frequencyRows(
      records
        .filter((record) => typeof record.year === "number" && Number.isFinite(record.year))
        .map((record) => {
          const decade = Math.floor((record.year as number) / 10) * 10;
          return {
            key: `${decade}s`,
            href: null,
          };
        }),
      Number.POSITIVE_INFINITY,
      "key",
    );
    const taxonomy = group.taxonomyFigures.map((figure) => ({
      name: figure.canonical_name,
      cluster: humanizeArchiveCode(figure.cluster),
      humanoidDegree: humanizeArchiveCode(figure.humanoid_degree),
      status: humanizeArchiveCode(figure.include_status),
      description: figure.description,
      sensitivityNote: figure.sensitivity_notes,
    }));
    const related = relatedEncyclopediaFigures(data, group, RELATED_PREVIEW_LIMIT).map((item) => ({
      href: figurePath(item.slug),
      label: item.label,
      recordCount: item.records.length,
    }));
    const aliases = group.aliases.slice(0, 24);
    const printedLabels = group.printedLabels.slice(0, 24);
    const searchText = [
      group.label,
      ...aliases,
      ...printedLabels,
      group.profile.shortDescription,
      ...taxonomy.flatMap((item) => [item.name, item.cluster, item.humanoidDegree]),
      ...narratives.map((item) => item.label),
    ]
      .join(" ")
      .toLowerCase();
    const mappedCount = records.filter(
      (record) =>
        record.has_strict_map_point ||
        (typeof record.map_latitude === "number" && typeof record.map_longitude === "number"),
    ).length;
    const dateSpan = years.length ? `${Math.min(...years)}–${Math.max(...years)}` : "Undated";

    return {
      slug: group.slug,
      label: group.label,
      description: group.profile.shortDescription,
      editorialSummary: buildEditorialSummary({
        label: group.label,
        description: group.profile.shortDescription,
        archiveDescription: group.profile.archiveDescription,
        recordCount: records.length,
        dateSpan,
        leadingRegion: regionFrequency[0] ?? null,
        leadingSource: sourceFrequency[0] ?? null,
        narrativeCodes,
        taxonomyDescription: taxonomy[0]?.description ?? null,
      }),
      aliases,
      printedLabels,
      rank: index + 1,
      recordCount: records.length,
      sourceCount: sources.length,
      placeCount: places.length,
      mappedCount,
      corpusShare: data.summary.record_count
        ? Number(((records.length / data.summary.record_count) * 100).toFixed(2))
        : 0,
      corpusTotal: data.summary.record_count,
      dateSpan,
      indexEligible: group.indexEligible,
      nameFrequency,
      regionFrequency,
      periodFrequency,
      sourceFrequency,
      narrativeFrequency,
      timeline,
      narratives,
      places,
      sources: sources.slice(0, 12),
      periods,
      records: records.slice(0, RECORD_PREVIEW_LIMIT).map((record) => ({
        href: recordPath(record),
        title: record.title || `Public record #${record.record_id}`,
        year: record.year,
        source: record.source_name || "Unspecified source",
        place: record.state_territory
          ? STATE_NAMES[record.state_territory] ?? record.state_territory
          : null,
        narrative: narrativeTypeName(record.ontology_code || record.genre || "unspecified"),
      })),
      related,
      taxonomy,
      externalReference: {
        href: group.profile.externalUrl,
        label: group.profile.referenceLabel,
      },
      searchText,
    };
  });
}

function buildEditorialSummary({
  label,
  description,
  archiveDescription,
  recordCount,
  dateSpan,
  leadingRegion,
  leadingSource,
  narrativeCodes,
  taxonomyDescription,
}: {
  label: string;
  description: string;
  archiveDescription?: string;
  recordCount: number;
  dateSpan: string;
  leadingRegion: FigureDictionaryFrequency | null;
  leadingSource: FigureDictionaryFrequency | null;
  narrativeCodes: Array<{ code: string; count: number }>;
  taxonomyDescription: string | null;
}) {
  const base = ensureSentence(
    archiveDescription ||
      buildNarrativeDescription(label, narrativeCodes, recordCount, taxonomyDescription) ||
      meaningfulProfileDescription(description),
  );

  if (!recordCount) {
    return `${base} No search-ready public record is currently available for a distribution summary, so this entry remains taxonomy-led.`;
  }

  const recordLabel = recordCount === 1 ? "record" : "records";
  const span = dateSpan === "Undated" ? "" : ` from ${dateSpan}`;
  const regionalClause = leadingRegion
    ? `The largest coded regional group is ${leadingRegion.label} (${formatSummaryCount(leadingRegion.count)})`
    : "No regional concentration is currently coded";
  const sourceClause = leadingSource
    ? `, and the largest source group is ${leadingSource.label} (${formatSummaryCount(leadingSource.count)})`
    : "";

  return `${base} The accepted archive contains ${formatSummaryCount(recordCount)} ${recordLabel}${span}. ${regionalClause}${sourceClause}. These distributions describe archive coverage, not real-world incidence.`;
}

const BROAD_DESCRIPTOR_LABELS = new Set([
  "haunted",
  "little man",
  "little woman",
  "most haunted",
  "supernatural",
]);

function buildNarrativeDescription(
  label: string,
  narrativeCodes: Array<{ code: string; count: number }>,
  recordCount: number,
  taxonomyDescription: string | null,
) {
  const normalizedLabel = label.trim().toLocaleLowerCase("en-AU").replace(/[_-]+/g, " ");
  const summaryLabel = label ? `${label.charAt(0).toLocaleUpperCase("en-AU")}${label.slice(1)}` : label;
  const top = narrativeCodes[0];
  const secondary = narrativeCodes[1];

  if (BROAD_DESCRIPTOR_LABELS.has(normalizedLabel)) {
    const narrativeContext = top
      ? ` The matched records most often sit within the “${narrativeTypeName(top.code)}” archive category`
      : "";
    const secondaryContext =
      secondary && secondary.count / Math.max(recordCount, 1) >= 0.2
        ? `, with the “${narrativeTypeName(secondary.code)}” category also present`
        : "";
    return `“${label}” functions here as a recurring printed descriptor rather than one stable named figure.${narrativeContext}${secondaryContext}; ordinary, literary, and supernatural uses may coexist, so the entry should not be read as a single sighting tradition.`;
  }

  if (!top) {
    return taxonomyDescription?.trim() || "";
  }

  const descriptionByCode: Record<string, string> = {
    apparition_account:
      `${summaryLabel} appears mainly in apparition accounts describing a visible human-like figure, voice, silhouette, or presence connected to a person or place.`,
    cryptid_style_apeman:
      `${summaryLabel} appears mainly in reports of a hairy or ape-like humanoid encountered in bush, roadside, or settlement-edge settings, often through a brief visual sighting, tracks, sounds, or witness reaction.`,
    descriptive_belief_record:
      `${summaryLabel} appears mainly in descriptive belief records that set out a named figure's role, attributes, relationships, or ceremonial context rather than presenting a modern eyewitness sighting.`,
    encounter_account:
      `${summaryLabel} appears mainly in reported encounters that preserve details such as appearance, movement, location, duration, or the witness's immediate response.`,
    giant_or_ogre_narrative:
      `${summaryLabel} appears mainly in giant or ogre narratives describing an oversized human-shaped figure, unusual strength, large tracks, or a threatening legendary presence.`,
    local_legend:
      `${summaryLabel} appears mainly as a place-linked local legend, where a named figure or recurring presence is attached to a road, building, landscape feature, or community retelling.`,
    retelling_or_adaptation:
      `${summaryLabel} appears mainly through literary retellings and later adaptations, so the archive records how the figure was repeated and reshaped rather than a direct encounter sequence.`,
    sighting_report:
      `${summaryLabel} appears mainly in sighting reports that describe what witnesses believed they saw, where the encounter occurred, and the figure's visible form or behaviour.`,
    spirit_person_narrative:
      `${summaryLabel} appears mainly in spirit-person narratives describing a human-like, named, ancestral, or otherwise culturally specific person whose role and appearance depend on the source tradition.`,
    traditional_narrative:
      `${summaryLabel} appears mainly in traditional narratives that describe a named or human-like being through story, place, kinship, law, or ceremonial context rather than a modern sighting format.`,
  };
  const primary =
    descriptionByCode[top.code] ||
    (taxonomyDescription?.trim()
      ? `${ensureSentence(taxonomyDescription)} Records most often place the figure in ${narrativeTypeName(top.code).toLocaleLowerCase("en-AU")} material.`
      : `${summaryLabel} appears most often in ${narrativeTypeName(top.code).toLocaleLowerCase("en-AU")} records, which preserve how the figure is described and situated in public sources.`);
  const secondaryClause =
    secondary && secondary.count / Math.max(recordCount, 1) >= 0.2
      ? ` A substantial secondary group (${formatSummaryCount(secondary.count)} records) comes from the “${narrativeTypeName(secondary.code)}” archive category, so the archive does not present the label as one uniform account type.`
      : "";

  return `${primary}${secondaryClause}`;
}

function meaningfulProfileDescription(description: string) {
  if (
    description.includes("is represented here as a public-text figure category") ||
    description.includes("This card summarises how records")
  ) {
    return "This dictionary entry groups source-grounded public descriptions under a shared printed figure label.";
  }
  return description;
}

function ensureSentence(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`;
}

function formatSummaryCount(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}

function frequencyCodeRows(records: FrontendData["records"]) {
  const counts = new Map<string, number>();
  for (const record of records) {
    const code = record.ontology_code || record.genre;
    if (!code) {
      continue;
    }
    counts.set(code, (counts.get(code) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([code, count]) => ({ code, count }))
    .sort((a, b) => b.count - a.count || a.code.localeCompare(b.code, "en-AU"));
}

function frequencyRows(
  items: Array<{ key: string; href: string | null }>,
  limit: number,
  sortMode: "count" | "key" = "count",
): FigureDictionaryFrequency[] {
  const counts = new Map<string, FigureDictionaryFrequency>();
  for (const item of items) {
    const key = cleanFrequencyLabel(item.key);
    if (!key) {
      continue;
    }
    const lookup = key.toLocaleLowerCase("en-AU");
    const existing = counts.get(lookup);
    if (existing) {
      existing.count += 1;
      if (!existing.href && item.href) {
        existing.href = item.href;
      }
      continue;
    }
    counts.set(lookup, {
      label: key,
      count: 1,
      href: item.href,
    });
  }
  return [...counts.values()]
    .sort((a, b) =>
      sortMode === "key"
        ? a.label.localeCompare(b.label, "en-AU", { numeric: true })
        : b.count - a.count || a.label.localeCompare(b.label, "en-AU"),
    )
    .slice(0, Number.isFinite(limit) ? limit : undefined);
}

function cleanFrequencyLabel(value: string) {
  return value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
}

function uniqueLinks(items: FigureDictionaryLink[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.href)) {
      return false;
    }
    seen.add(item.href);
    return true;
  });
}
