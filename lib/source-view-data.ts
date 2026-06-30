import type { FrontendData, RecordItem, SourceItem } from "@/lib/types";

export const SOURCE_FAMILY_STYLES = {
  repository: {
    label: "Repository / archive",
    marker: "bar",
    color: "#0B7F6C",
    stroke: "#0B7F6C",
    fill: "#4FAE9E",
    soft: "#D9F0EA",
    role: "Repository source",
  },
  modern_web: {
    label: "Modern public web",
    marker: "square",
    color: "#2F5FB8",
    stroke: "#2F5FB8",
    fill: "#6F8ED8",
    soft: "#DDE7FF",
    role: "Public web source",
  },
  public_domain: {
    label: "Public-domain text",
    marker: "tick",
    color: "#B76A12",
    stroke: "#B76A12",
    fill: "#D99A3B",
    soft: "#F5E4C7",
    role: "Public-domain source",
  },
  institutions: {
    label: "Public institution",
    marker: "square",
    color: "#7357B8",
    stroke: "#7357B8",
    fill: "#9A7BD1",
    soft: "#E7DFF6",
    role: "Institutional source",
  },
  academic: {
    label: "Academic / catalogue metadata",
    marker: "dot",
    color: "#6D65B8",
    stroke: "#6D65B8",
    fill: "#8D86CF",
    soft: "#E4E1F5",
    role: "Metadata source",
  },
  community: {
    label: "Community-controlled public source",
    marker: "hollow",
    color: "#2B7FAE",
    stroke: "#2B7FAE",
    fill: "#6AAED0",
    soft: "#D9EDF6",
    role: "Community source",
  },
  other: {
    label: "Other public source",
    marker: "hollow",
    color: "#666D73",
    stroke: "#666D73",
    fill: "#9AA1A6",
    soft: "#E6E8EA",
    role: "Public source",
  },
} as const;

export type SourceFamilyId = keyof typeof SOURCE_FAMILY_STYLES;

export type SourceRollupRow = {
  id: SourceFamilyId;
  label: string;
  color: string;
  marker: string;
  records: number;
  share: number;
  orgs: number;
};

export type SourceTypeRollupRow = {
  id: string;
  label: string;
  familyLabel: string;
  color: string;
  records: number;
  orgs: number;
};

export type SourceRegistryRow = {
  source: SourceItem;
  familyId: SourceFamilyId;
  familyLabel: string;
  color: string;
  publicRole: string;
  displayType: string;
  recordCount: number;
  yearStart: number | null;
  yearEnd: number | null;
  narrativeLabels: string[];
  jurisdictions: string[];
  searchableText: string;
};

export type SourceRegistryData = {
  metrics: {
    sourceOrgs: number;
    publicRecords: number;
    sourceTypes: number;
  };
  rollupRows: SourceRollupRow[];
  typeRows: SourceTypeRollupRow[];
  registryRows: SourceRegistryRow[];
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  academic_metadata: "Academic metadata",
  aiatsis_public_catalogue: "Public catalogue",
  community_controlled_public_web: "Community public web",
  institutional_education_page: "Institutional education page",
  institutional_history_and_media_pages: "Institutional history/media",
  institutional_history_article: "Institutional history article",
  institutional_history_page: "Institutional history page",
  institutional_media_page: "Institutional media page",
  institutional_web: "Institutional web",
  internet_archive_metadata: "Archive metadata",
  internet_sacred_texts_public_domain_book: "Public-domain text",
  live_crawl_crossref: "Crossref metadata",
  live_crawl_openalex: "OpenAlex metadata",
  modern_web: "Modern public web",
  municipal_local_history_pdf: "Local history PDF",
  project_gutenberg_australia_book: "Public-domain book",
  public_books_metadata_openlibrary: "Open Library metadata",
  public_domain_ebook: "Public-domain book",
  public_domain_transcribed_book: "Public-domain text",
  public_repository_newsletter_ocr_text: "Repository OCR text",
  public_repository_ocr_text: "Repository OCR text",
  public_web_haunted_places_directory: "Haunted places directory",
  public_web_yowie_report_map: "Yowie report map",
  public_web_yowie_state_report_index: "Yowie state report index",
  public_wikidata_entity_metadata: "Wikidata metadata",
  repository_full_text: "Full text",
  repository_full_text_article: "Repository article",
  repository_institutional_full_text: "Institutional full text",
  seeded_public_web: "Public web",
  wikisource_public_domain_book: "Public-domain text",
};

const NARRATIVE_LABELS: Record<string, string> = {
  ancestral_being: "Ancestral being",
  apparition_account: "Apparition account",
  cautionary_being: "Cautionary being",
  cryptid_style_apeman: "Hairy humanoid",
  descriptive_belief_record: "Belief record",
  encounter_account: "Encounter account",
  ghost_legend: "Ghost legend",
  giant: "Giant narrative",
  giant_or_ogre_narrative: "Giant / ogre narrative",
  local_legend: "Local legend",
  non_humanoid_control: "Control record",
  retelling_or_adaptation: "Retelling / adaptation",
  rumour_account: "Rumour account",
  satire: "Satire",
  spirit_being: "Spirit being",
  spirit_person_narrative: "Spirit-person narrative",
  traditional_narrative: "Traditional narrative",
};

export function buildSourceRegistryData(data: FrontendData): SourceRegistryData {
  const sourceRecords = new Map<number, RecordItem[]>();
  const sourceTypeSet = new Set<string>();

  for (const source of data.sources) {
    sourceRecords.set(source.source_id, []);
    sourceTypeSet.add(source.source_type);
  }

  for (const record of data.records) {
    const rows = sourceRecords.get(record.source_id);
    if (rows) {
      rows.push(record);
    }
    if (record.source_type) {
      sourceTypeSet.add(record.source_type);
    }
  }

  const registryRows = data.sources
    .map((source) => buildRegistryRow(source, sourceRecords.get(source.source_id) ?? []))
    .sort((a, b) => b.recordCount - a.recordCount || a.source.source_name.localeCompare(b.source.source_name));

  const rollupMap = new Map<SourceFamilyId, SourceRollupRow>();
  for (const id of Object.keys(SOURCE_FAMILY_STYLES) as SourceFamilyId[]) {
    const style = SOURCE_FAMILY_STYLES[id];
    rollupMap.set(id, {
      id,
      label: style.label,
      color: style.color,
      marker: style.marker,
      records: 0,
      share: 0,
      orgs: 0,
    });
  }

  for (const row of registryRows) {
    const rollup = rollupMap.get(row.familyId);
    if (!rollup) {
      continue;
    }
    rollup.records += row.recordCount;
    rollup.orgs += 1;
  }

  const publicRecords = data.summary.record_count || data.records.length;
  const rollupRows = [...rollupMap.values()]
    .map((row) => ({
      ...row,
      share: publicRecords ? Math.round((row.records / publicRecords) * 100) : 0,
    }))
    .filter((row) => row.records > 0)
    .sort((a, b) => b.records - a.records || a.label.localeCompare(b.label));

  const typeRows = buildTypeRows(registryRows).slice(0, 18);

  return {
    metrics: {
      sourceOrgs: data.summary.source_count || data.sources.length,
      publicRecords,
      sourceTypes: sourceTypeSet.size,
    },
    rollupRows,
    typeRows,
    registryRows,
  };
}

function buildTypeRows(registryRows: SourceRegistryRow[]): SourceTypeRollupRow[] {
  const typeMap = new Map<string, SourceTypeRollupRow>();

  for (const row of registryRows) {
    const id = row.displayType;
    const existing = typeMap.get(id);
    if (existing) {
      existing.records += row.recordCount;
      existing.orgs += 1;
      continue;
    }
    typeMap.set(id, {
      id,
      label: row.displayType,
      familyLabel: row.familyLabel,
      color: row.color,
      records: row.recordCount,
      orgs: 1,
    });
  }

  return [...typeMap.values()].sort((a, b) => b.records - a.records || a.label.localeCompare(b.label));
}

function buildRegistryRow(source: SourceItem, records: RecordItem[]): SourceRegistryRow {
  const familyId = sourceFamilyId(source.source_type);
  const style = SOURCE_FAMILY_STYLES[familyId];
  const years = records
    .map((record) => record.year)
    .filter((year): year is number => typeof year === "number" && Number.isFinite(year));
  const narratives = new Set<string>();
  const jurisdictions = new Set<string>();

  for (const record of records) {
    const narrativeKey = record.ontology_code || record.genre || record.canonical_figure_guess || record.canonical_figure;
    if (narrativeKey) {
      narratives.add(displayNarrativeLabel(narrativeKey));
    }
    if (record.state_territory) {
      jurisdictions.add(record.state_territory);
    }
  }

  const displayType = displaySourceType(source.source_type);
  const publicRole = publicSourceRole(source, familyId);

  return {
    source,
    familyId,
    familyLabel: style.label,
    color: style.color,
    publicRole,
    displayType,
    recordCount: records.length,
    yearStart: years.length ? Math.min(...years) : null,
    yearEnd: years.length ? Math.max(...years) : null,
    narrativeLabels: [...narratives].sort(),
    jurisdictions: [...jurisdictions].sort(),
    searchableText: [
      source.source_name,
      source.source_type,
      source.publicness_level,
      publicRole,
      displayType,
      style.label,
    ].join(" ").toLowerCase(),
  };
}

export function sourceFamilyId(sourceType: string | null | undefined): SourceFamilyId {
  const source = (sourceType ?? "").toLowerCase();
  if (/community/.test(source)) {
    return "community";
  }
  if (/repository|archive|trove|newspaper|magazine/.test(source)) {
    return "repository";
  }
  if (/modern_web|seeded_public_web|public_web|haunted_places|yowie_report|yowie_state/.test(source)) {
    return "modern_web";
  }
  if (/public_domain|gutenberg|wikisource|sacred_texts/.test(source)) {
    return "public_domain";
  }
  if (/institutional|municipal/.test(source)) {
    return "institutions";
  }
  if (/academic|catalogue|metadata|andc|openalex|crossref|wikidata|openlibrary/.test(source)) {
    return "academic";
  }
  return "other";
}

export function displaySourceType(sourceType: string | null | undefined) {
  if (!sourceType) {
    return "Public source";
  }
  return SOURCE_TYPE_LABELS[sourceType] ?? titleize(sourceType);
}

function publicSourceRole(source: SourceItem, familyId: SourceFamilyId) {
  const publicness = (source.publicness_level ?? "").toLowerCase();
  if (/metadata|catalogue/.test(publicness)) {
    return "Metadata source";
  }
  if (/public_domain/.test(publicness)) {
    return "Public-domain source";
  }
  if (/media/.test(publicness)) {
    return "Public media source";
  }
  return SOURCE_FAMILY_STYLES[familyId].role;
}

function displayNarrativeLabel(value: string) {
  return NARRATIVE_LABELS[value] ?? titleize(value);
}

function titleize(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
