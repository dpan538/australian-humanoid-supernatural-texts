"use client";

import { CSSProperties, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import Link from "next/link";
import { createTimeline, stagger } from "animejs";
import type { Timeline } from "animejs";
import type { DateBand, FrontendData, MapFlagItem, RecordItem } from "@/lib/types";
import { MAP_BOUNDARY_SOURCE, MAP_VIEWBOX, STATE_SHAPES, TERRAIN_TILES } from "@/lib/au-map-data";
import { FRONTEND_DATA_SCHEMA, FRONTEND_DATA_URL } from "@/lib/frontend-data";
import { buildDensityPeriodSchemes, periodContainsYear } from "@/lib/density-periods";
import type { DensityPeriod, DensityPeriodScheme, DensityPeriodSchemeId } from "@/lib/density-periods";
import { SourceView } from "@/components/source/source-view";
import { DisplayControls } from "@/components/signal-gain-control";

export type ViewMode = "map" | "density" | "dashboard" | "source";

const VIEW_SEQUENCE: ViewMode[] = ["dashboard", "map", "density"];

const VIEW_LABELS: Record<ViewMode, string> = {
  dashboard: "Dashboard",
  map: "Map",
  density: "Density",
  source: "Source",
};

const VIEW_PATHS: Record<ViewMode, string> = {
  dashboard: "/dashboard",
  map: "/map",
  density: "/density",
  source: "/source",
};

const STATE_NAMES: Record<string, string> = {
  WA: "Western Australia",
  NT: "Northern Territory",
  SA: "South Australia",
  QLD: "Queensland",
  NSW: "New South Wales",
  VIC: "Victoria",
  TAS: "Tasmania",
  ACT: "Australian Capital Territory",
};

const SOURCE_TONE: Record<string, { label: string; className: string }> = {
  trove_newspaper: { label: "NEWSPAPER", className: "source-tone-newspaper" },
  trove_magazine: { label: "MAGAZINE", className: "source-tone-magazine" },
  nla_catalogue: { label: "CATALOGUE", className: "source-tone-catalogue" },
  aiatsis_public_catalogue: { label: "CATALOGUE", className: "source-tone-catalogue" },
  andc: { label: "METADATA", className: "source-tone-metadata" },
  academic_metadata: { label: "ACADEMIC", className: "source-tone-academic" },
  internet_archive_metadata: { label: "ARCHIVE", className: "source-tone-archive" },
  institutional_web: { label: "INSTITUTIONAL", className: "source-tone-institutional" },
  seeded_public_web: { label: "PUBLIC WEB", className: "source-tone-seeded-web" },
  google_trends: { label: "ATTENTION", className: "source-tone-attention" },
  wikimedia_pageviews: { label: "PAGEVIEWS", className: "source-tone-attention" },
  modern_web: { label: "WEB", className: "source-tone-web" },
  manual: { label: "MANUAL", className: "source-tone-manual" },
};

const SOURCE_PUBLIC_LABELS: Record<string, string> = {
  trove_newspaper: "Historic newspapers",
  trove_magazine: "Historic magazines",
  nla_catalogue: "Library catalogues",
  aiatsis_public_catalogue: "Public catalogues",
  andc: "Research metadata",
  academic_metadata: "Scholarly metadata",
  internet_archive_metadata: "Archive metadata",
  institutional_web: "Public institutions",
  seeded_public_web: "Public web",
  modern_web: "Modern web",
  public_domain_ebook: "Public-domain books",
  repository_full_text: "Repository text",
  repository_full_text_article: "Repository articles",
  repository_institutional_full_text: "Institutional repositories",
  project_gutenberg_australia_book: "Public-domain books",
  public_domain_transcribed_book: "Public-domain books",
  wikisource_public_domain_book: "Public-domain books",
  internet_sacred_texts_public_domain_book: "Public-domain books",
  institutional_media_page: "Public institutions",
  institutional_history_article: "Public institutions",
  institutional_history_page: "Public institutions",
  community_controlled_public_web: "Community public web",
  google_trends: "Public attention",
  wikimedia_pageviews: "Pageviews",
  manual: "Manual review",
};

const MAP_SOURCE_LEGEND_GROUPS = [
  { id: "repository", label: "Repository / archive", className: "source-tone-archive" },
  { id: "public-domain", label: "Public-domain text", className: "source-tone-candidate" },
  { id: "modern-web", label: "Modern public web", className: "source-tone-web" },
  { id: "institution", label: "Public institution", className: "source-tone-institutional" },
  { id: "other", label: "Other public source", className: "source-tone-default" },
] as const;

const MAP_FLAG_GROWTH_BUCKETS = [
  { start: -Infinity, end: 1841 },
  { start: 1842, end: 1875 },
  { start: 1876, end: 1900 },
  { start: 1901, end: 1950 },
  { start: 1951, end: 1969 },
  { start: 1970, end: 1990 },
  { start: 1991, end: 2010 },
  { start: 2011, end: Infinity },
] as const;

const NARRATIVE_TYPE_LABELS: Record<string, string> = {
  cryptid_style_apeman: "Hairy humanoid reports",
  encounter_account: "Encounter accounts",
  apparition_account: "Ghost / apparition",
  ghost_legend: "Ghost / apparition",
  local_legend: "Local legends",
  rumour_account: "Rumours",
  traditional_narrative: "Traditional narratives",
  spirit_person_narrative: "Spirit-person narratives",
  giant_or_ogre_narrative: "Giant / ogre narratives",
  descriptive_belief_record: "Belief records",
  retelling_or_adaptation: "Retellings",
};

const DENSITY_CHARS = [" ", ".", ":", "+", "#"];
const TERRAIN_SYMBOLS = {
  range: "+",
  plateau: "@",
  upland: "#",
  lowland: "o",
  desert: ".",
  plain: "_",
  basin: "$",
} as const;

type TerrainKind = keyof typeof TERRAIN_SYMBOLS;
type DashboardLayout = "balanced" | "left-expanded" | "right-expanded";
type ConsoleMode = "records" | "locations" | "sources";
type ConsoleChartPoint = {
  key: string;
  label: string;
  value: number;
};
type TimelineLayerPoint = ConsoleChartPoint & {
  mapped: number;
  diversity: number;
};
type RelationLane = "source" | "period" | "narrative" | "place";
type RelationNode = {
  id: string;
  lane: RelationLane;
  key: string;
  label: string;
  count: number;
  x: number;
  y: number;
  relationKey: string;
  sourceClass?: string;
};
type RelationEdge = {
  key: string;
  from: string;
  to: string;
  kind: "source-period" | "period-narrative" | "narrative-place";
  count: number;
  sourceLabel?: string;
};
type RelationGroup = {
  key: string;
  source: string;
  periodId: string;
  periodLabel: string;
  narrative: string;
  place: string;
  count: number;
  records: RecordItem[];
  placeCounts: Record<string, number>;
};
const DASHBOARD_STATE_ORDER = ["WA", "NT", "SA", "QLD", "NSW", "VIC", "TAS", "ACT"] as const;
const NARRATIVE_MATRIX_LABELS = [
  "Hairy humanoid reports",
  "Spirit-person narratives",
  "Ghost / apparition records",
  "Traditional narratives",
  "Retellings and adaptations",
  "Giant / ogre narratives",
  "Local legends",
  "Encounter accounts",
  "Other typed context",
] as const;
const PRECISION_LABELS = [
  "Exact site",
  "Road segment",
  "Named feature",
  "Locality",
  "Town / suburb",
  "Broad region",
  "Unmapped",
] as const;
const PLACE_ROLE_LABELS = [
  "Event location",
  "Apparition location",
  "Legend-associated place",
  "Narrative setting",
  "Rumour circulation place",
] as const;
const SOURCE_FAMILIES = [
  { id: "repository", label: "Repository texts", color: "#69d7d0" },
  { id: "modern_web", label: "Modern public web", color: "#eceae2" },
  { id: "public_domain", label: "Public-domain books", color: "#d9a854" },
  { id: "institutions", label: "Public institutions", color: "#98df63" },
  { id: "academic", label: "Academic / catalogue sources", color: "#9580cf" },
  { id: "community", label: "Community-controlled public sources", color: "#7fb8ff" },
  { id: "other", label: "Other", color: "#7f858a" },
] as const;

type MatrixCell = {
  bandId: string;
  bandLabel: string;
  value: number;
};
type NarrativePeriodRow = {
  label: string;
  values: MatrixCell[];
};
type DensityAnalysisTab = "temporal_narrative" | "source_bias" | "map_coverage" | "regional_profile";
type DensityPeriodSummary = {
  period: DensityPeriod;
  records: RecordItem[];
  mappedCount: number;
  topNarrative: string;
  topSourceFamily: string;
  firstRecord: RecordItem | null;
};
type DensityNarrativeCard = {
  label: string;
  records: RecordItem[];
  mappedCount: number;
  topSourceFamily: string;
  dateSpan: string;
  description: string;
  glyph: string;
  sensitivityNote: string;
};
type StateCoverageRow = {
  state: string;
  total: number;
  mapped: number;
};
type PrecisionRow = {
  label: string;
  value: number;
};
type PlaceRoleRow = {
  label: string;
  values: MatrixCell[];
};
type SourceFamilyAggregate = {
  id: string;
  label: string;
  color: string;
  count: number;
  byBand: Record<string, number>;
};
type DashboardFieldAggregate = {
  dateBands: readonly DateBand[];
  totalRecords: number;
  totalMapped: number;
  timeline: TimelineLayerPoint[];
  narrativePeriodRows: NarrativePeriodRow[];
  topNarratives: Array<{ label: string; value: number }>;
  representativeRecords: RecordItem[];
  stateRows: StateCoverageRow[];
  precisionRows: PrecisionRow[];
  placeRoleRows: PlaceRoleRow[];
  sourceFamilies: SourceFamilyAggregate[];
};

const TERRAIN_KINDS = Object.keys(TERRAIN_SYMBOLS) as TerrainKind[];
const TERRAIN_LABELS: Record<TerrainKind, string> = {
  range: "RANGE",
  plateau: "PLATEAU",
  upland: "UPLAND",
  lowland: "LOWLAND",
  desert: "DESERT",
  plain: "PLAIN",
  basin: "BASIN",
};

const STATE_LABEL_OVERRIDES: Partial<Record<keyof typeof STATE_NAMES, [number, number]>> = {
  SA: [520, 402],
  NSW: [733, 479],
  VIC: [688, 552],
  TAS: [714, 654],
  ACT: [784, 512],
};

const STATE_CLUSTER_POSITIONS: Record<string, [number, number]> = {
  WA: [246, 356],
  NT: [412, 262],
  SA: [520, 389],
  QLD: [682, 322],
  NSW: [720, 482],
  VIC: [660, 548],
  TAS: [704, 642],
  ACT: [784, 512],
};

const STATE_TERRAIN_KINDS = TERRAIN_TILES.reduce<Record<string, TerrainKind[]>>((acc, tile) => {
  if (!TERRAIN_KINDS.includes(tile.kind as TerrainKind)) {
    return acc;
  }
  const kind = tile.kind as TerrainKind;
  const stateKinds = acc[tile.state] ?? [];
  if (!stateKinds.includes(kind)) {
    stateKinds.push(kind);
  }
  acc[tile.state] = stateKinds;
  return acc;
}, {});

const JSON_BOUNDS = {
  minX: -999,
  maxX: 8821,
  minY: 649,
  maxY: 9851,
} as const;

const SVG_BOUNDS = {
  minX: 54,
  maxX: 914,
  minY: 36,
  maxY: 676,
} as const;

const HICHARTS_AU_TRANSFORM = {
  scale: 0.000158093982027,
  jsonres: 15.5,
  jsonmarginX: -999,
  jsonmarginY: 9851,
  xoffset: -2082021.85219,
  yoffset: -1210304.51735,
} as const;

const LAMBERT_AU = {
  radius: 6378137,
  lat1: -18,
  lat2: -36,
  lat0: 0,
  lon0: 134,
} as const;

let frontendDataCache: FrontendData | null = null;
let frontendDataPromise: Promise<FrontendData> | null = null;

type MapFlagRenderItem = {
  flag_id: string;
  record_id: number;
  state_territory: string;
  x: number;
  y: number;
  displayX: number;
  displayY: number;
  collisionOffset: boolean;
  growthBucket: number;
  growthOrder: number;
  title: string | null;
  year: number | null;
  canonical_figure: string | null;
  record: RecordItem;
  toneClass: string;
};

type MapSourceLegendItem = {
  id: string;
  label: string;
  className: string;
  count: number;
};

type FrontendDerivedData = {
  recordsById: Map<number, RecordItem>;
  sortedRecords: RecordItem[];
  navigationRecordsByState: Map<string, RecordItem[]>;
  mapFlags: MapFlagRenderItem[];
  mapFlagRecordLookup: Map<number, MapFlagRenderItem>;
  mappedStateCounts: Record<string, number>;
  queryTypeCounts: Record<string, number>;
  figureCounts: Record<string, number>;
  figureSamples: Map<string, RecordItem>;
  firstRecordByDateBand: Map<string, RecordItem>;
  dateBandActualCounts: Record<string, number>;
  sourceRows: Array<[string, { record_count: number; query_count: number }]>;
  ethicsRows: Array<[string, number]>;
  dashboardTracks: RecordItem[];
  undatedRecordCount: number;
};

function loadFrontendData() {
  if (frontendDataCache) {
    return Promise.resolve(frontendDataCache);
  }
  if (!frontendDataPromise) {
    frontendDataPromise = fetch(FRONTEND_DATA_URL, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Frontend data request failed: ${response.status}`);
        }
        return response.json() as Promise<FrontendData>;
      })
      .then((payload) => {
        frontendDataCache = payload;
        return payload;
      });
  }
  return frontendDataPromise;
}

function numberFormat(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "--";
  }
  return new Intl.NumberFormat("en-AU").format(value);
}

function mapCount(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return String(Math.trunc(value));
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function svgCoord(value: number) {
  return Number(value.toFixed(3));
}

function truncate(value: string | null | undefined, length: number) {
  if (!value) {
    return "uncoded";
  }
  return value.length > length ? `${value.slice(0, length - 3)}...` : value;
}

function compactChartLabel(value: string, mode: ConsoleMode) {
  if (mode === "records") {
    const years = value.match(/\d{4}/g);
    if (!years?.length) {
      return value;
    }
    return years.length > 1 ? `${years[0]}-${years[years.length - 1].slice(2)}` : years[0];
  }
  if (mode === "locations") {
    return value;
  }
  const words = value.replace(/[_-]+/g, " ").split(/\s+/).filter(Boolean);
  if (words.length <= 1) {
    return truncate(value, 8);
  }
  return words.slice(0, 2).map((word) => word.slice(0, 4)).join(" ");
}

function relationKey(source: string, periodId: string, narrative: string) {
  return `${source}::${periodId}::${narrative}`;
}

function recordPeriod(data: FrontendData, record: RecordItem) {
  const band = data.date_bands.find((item) => item.id === record.date_band);
  return {
    id: record.date_band || "undated",
    label: band?.label ?? "Undated",
  };
}

function recordRelationParts(data: FrontendData, record: RecordItem) {
  const period = recordPeriod(data, record);
  const source = publicSourceLabel(record.source_type);
  const narrative = narrativeGroupLabel(record);
  const place = record.state_territory || "Broad / unmapped";
  return {
    source,
    periodId: period.id,
    periodLabel: period.label,
    narrative,
    place,
    key: relationKey(source, period.id, narrative),
  };
}

function sourceGraphClass(label: string) {
  const normalized = label.toLowerCase();
  if (/repository|institutional/.test(normalized)) {
    return "source-repository";
  }
  if (/public-domain|book|gutenberg/.test(normalized)) {
    return "source-public-domain";
  }
  if (/modern|web/.test(normalized)) {
    return "source-modern-web";
  }
  if (/academic|scholarly|metadata|catalogue/.test(normalized)) {
    return "source-academic";
  }
  if (/community/.test(normalized)) {
    return "source-community";
  }
  return "source-other";
}

function sourceGraphColor(label: string) {
  const sourceClass = sourceGraphClass(label);
  if (sourceClass === "source-repository" || sourceClass === "source-public-domain") {
    return "#69d7d0";
  }
  if (sourceClass === "source-academic") {
    return "#9580cf";
  }
  if (sourceClass === "source-community") {
    return "#d6a650";
  }
  if (sourceClass === "source-modern-web") {
    return "#eceae2";
  }
  return "rgba(236, 234, 226, 0.72)";
}

function relationPath(from: RelationNode | undefined, to: RelationNode | undefined) {
  if (!from || !to) {
    return "";
  }
  const startX = from.x + 56;
  const startY = from.y;
  const endX = to.x - 56;
  const endY = to.y;
  const control = (startX + endX) / 2;
  return `M ${startX} ${startY} C ${control} ${startY}, ${control} ${endY}, ${endX} ${endY}`;
}

function entriesDescending(values: Record<string, number>, limit?: number) {
  const entries = Object.entries(values).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return limit ? entries.slice(0, limit) : entries;
}

function conicGradient(values: Record<string, number>) {
  const palette = ["#f2f2ed", "#9fe36b", "#8ed8ff", "#d9a854", "#9480cf", "#7f858a", "#4b4f50"];
  const entries = entriesDescending(values);
  const total = entries.reduce((sum, [, value]) => sum + value, 0) || 1;
  let cursor = 0;
  return entries
    .map(([, value], index) => {
      const start = cursor;
      cursor += (value / total) * 100;
      return `${palette[index % palette.length]} ${start}% ${cursor}%`;
    })
    .join(", ");
}

function compareRecordsByDate(a: RecordItem, b: RecordItem) {
  const yearA = a.year ?? 9999;
  const yearB = b.year ?? 9999;
  return yearA - yearB || (a.title ?? "").localeCompare(b.title ?? "") || a.record_id - b.record_id;
}

function createFrontendDerivedData(data: FrontendData): FrontendDerivedData {
  const recordsById = new Map<number, RecordItem>();
  const navigationRecordsByState = new Map<string, RecordItem[]>();
  const queryTypeCounts: Record<string, number> = {};
  const figureCounts: Record<string, number> = {};
  const figureSamples = new Map<string, RecordItem>();
  const firstRecordByDateBand = new Map<string, RecordItem>();
  const dateBandActualCounts: Record<string, number> = {};
  let undatedRecordCount = 0;

  for (const record of data.records) {
    recordsById.set(record.record_id, record);
    const figure = record.canonical_figure_guess || record.canonical_figure || "uncoded";
    figureCounts[figure] = (figureCounts[figure] ?? 0) + 1;
    if (!figureSamples.has(figure)) {
      figureSamples.set(figure, record);
    }
    if (!firstRecordByDateBand.has(record.date_band)) {
      firstRecordByDateBand.set(record.date_band, record);
    }
    dateBandActualCounts[record.date_band] = (dateBandActualCounts[record.date_band] ?? 0) + 1;
    if (record.year === null || record.year === undefined) {
      undatedRecordCount += 1;
    }
    if (record.has_strict_map_point && record.state_territory) {
      const stateRecords = navigationRecordsByState.get(record.state_territory) ?? [];
      stateRecords.push(record);
      navigationRecordsByState.set(record.state_territory, stateRecords);
    }
  }

  for (const query of data.queries) {
    queryTypeCounts[query.query_type] = (queryTypeCounts[query.query_type] ?? 0) + 1;
  }

  const mapFlags = buildMapFlags(data, recordsById);
  for (const flag of mapFlags) {
    if (recordsById.has(flag.record_id)) {
      continue;
    }
    recordsById.set(flag.record_id, flag.record);
    const stateRecords = navigationRecordsByState.get(flag.state_territory) ?? [];
    stateRecords.push(flag.record);
    navigationRecordsByState.set(flag.state_territory, stateRecords);
  }
  const sortedRecords = [...recordsById.values()].sort(compareRecordsByDate);
  for (const records of navigationRecordsByState.values()) {
    records.sort(compareRecordsByDate);
  }
  const mappedStateCounts = mapFlags.reduce<Record<string, number>>((acc, flag) => {
    acc[flag.state_territory] = (acc[flag.state_territory] ?? 0) + 1;
    return acc;
  }, {});
  const mapFlagRecordLookup = new Map(mapFlags.map((flag) => [flag.record_id, flag]));

  return {
    recordsById,
    sortedRecords,
    navigationRecordsByState,
    mapFlags,
    mapFlagRecordLookup,
    mappedStateCounts,
    queryTypeCounts,
    figureCounts,
    figureSamples,
    firstRecordByDateBand,
    dateBandActualCounts,
    sourceRows: Object.entries(data.summary.source_rollup).sort(
      (a, b) => b[1].record_count - a[1].record_count || a[0].localeCompare(b[0]),
    ),
    ethicsRows: entriesDescending(data.summary.ethics_counts),
    dashboardTracks: dashboardTrackSample(data),
    undatedRecordCount,
  };
}

function buildMapFlags(data: FrontendData, recordsById: Map<number, RecordItem>) {
  const seenRecordIds = new Set<number>();
  const flags: MapFlagRenderItem[] = [];
  const sourceFlags = data.map_flags?.length ? data.map_flags : createFallbackMapFlags(data.records);

  for (const flag of sourceFlags) {
    const record = recordsById.get(flag.record_id) ?? createRecordFromMapFlag(flag, data.date_bands);
    const coordinates = mapFlagCoordinates(flag, record);
    if (!coordinates || seenRecordIds.has(flag.record_id)) {
      continue;
    }
    seenRecordIds.add(flag.record_id);
    flags.push({
      flag_id: flag.flag_id,
      record_id: flag.record_id,
      state_territory: flag.state_territory || record.state_territory || "AU",
      x: coordinates.x,
      y: coordinates.y,
      displayX: coordinates.x,
      displayY: coordinates.y,
      collisionOffset: false,
      growthBucket: 0,
      growthOrder: 0,
      title: flag.title ?? record.title,
      year: flag.year ?? record.year,
      canonical_figure: flag.canonical_figure ?? record.canonical_figure_guess ?? record.canonical_figure,
      record,
      toneClass: mapSourceTone(record).className,
    });
  }

  return prepareMapFlagPresentation(flags);
}

function prepareMapFlagPresentation(flags: MapFlagRenderItem[]) {
  const collisionGroups = new Map<string, MapFlagRenderItem[]>();

  for (const flag of flags) {
    flag.growthBucket = chronologicalGrowthBucket(flag);
    const collisionKey = `${flag.x.toFixed(3)}:${flag.y.toFixed(3)}`;
    const group = collisionGroups.get(collisionKey) ?? [];
    group.push(flag);
    collisionGroups.set(collisionKey, group);
  }

  const chronologicalFlags = [...flags].sort((a, b) => (
    a.growthBucket - b.growthBucket ||
    (a.year ?? Number.MAX_SAFE_INTEGER) - (b.year ?? Number.MAX_SAFE_INTEGER) ||
    a.record_id - b.record_id
  ));
  chronologicalFlags.forEach((flag, index) => {
    flag.growthOrder = index;
  });

  for (const group of collisionGroups.values()) {
    if (group.length < 2) {
      continue;
    }
    const ordered = [...group].sort((a, b) => a.record_id - b.record_id);
    ordered.forEach((flag, index) => {
      const offset = collisionMicroJitter(flag.record_id, index);
      flag.displayX = flag.x + offset.x;
      flag.displayY = flag.y + offset.y;
      flag.collisionOffset = true;
    });
  }

  return flags;
}

function chronologicalGrowthBucket(flag: MapFlagRenderItem) {
  if (typeof flag.year === "number" && Number.isFinite(flag.year)) {
    const bucketIndex = MAP_FLAG_GROWTH_BUCKETS.findIndex((bucket) => flag.year !== null && flag.year >= bucket.start && flag.year <= bucket.end);
    return bucketIndex >= 0 ? bucketIndex : MAP_FLAG_GROWTH_BUCKETS.length - 1;
  }
  const bandOrder = ["backsearch_1803_1841", "anchor_1842_1875", "expansion_1876_1969", "modern_1970_1990", "modern_1991_2010", "contemporary_2011_present"];
  const bandIndex = bandOrder.indexOf(flag.record.date_band);
  if (bandIndex < 0) {
    return MAP_FLAG_GROWTH_BUCKETS.length - 1;
  }
  return Math.round((bandIndex / Math.max(1, bandOrder.length - 1)) * (MAP_FLAG_GROWTH_BUCKETS.length - 1));
}

function stableUnit(seed: number) {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

function collisionMicroJitter(recordId: number, collisionIndex: number) {
  if (collisionIndex === 0) {
    return { x: 0, y: 0 };
  }
  const xUnit = stableUnit(recordId + collisionIndex * 97);
  const yUnit = stableUnit(recordId * 3 + collisionIndex * 193);
  const x = (xUnit - 0.5) * 4.2;
  const y = (yUnit - 0.5) * 3.8;
  return {
    x: svgCoord(clamp(x, -2.1, 2.1)),
    y: svgCoord(clamp(y, -1.9, 1.9)),
  };
}

function buildMapSourceLegend(mapFlags: readonly MapFlagRenderItem[]): MapSourceLegendItem[] {
  const counts = new Map<string, number>();
  for (const flag of mapFlags) {
    const group = mapSourceLegendGroup(flag.record);
    counts.set(group.id, (counts.get(group.id) ?? 0) + 1);
  }

  return MAP_SOURCE_LEGEND_GROUPS.map((group) => ({
    ...group,
    count: counts.get(group.id) ?? 0,
  })).filter((group) => group.count > 0);
}

function mapSourceLegendGroup(record: RecordItem) {
  const text = [record.source_type, record.source_name, record.publication, record.url].filter(Boolean).join(" ").toLowerCase();
  if (/public_domain|gutenberg|wikisource|sacred_texts/.test(text)) {
    return MAP_SOURCE_LEGEND_GROUPS[1];
  }
  if (/institutional|municipal|museum|library|catalogue|aiatsis|abc|parks victoria/.test(text)) {
    return MAP_SOURCE_LEGEND_GROUPS[3];
  }
  if (/repository|archive|trove|newspaper|magazine/.test(text)) {
    return MAP_SOURCE_LEGEND_GROUPS[0];
  }
  if (/modern_web|seeded_public_web|yowie research|public_web|web/.test(text)) {
    return MAP_SOURCE_LEGEND_GROUPS[2];
  }
  return MAP_SOURCE_LEGEND_GROUPS[4];
}

function createRecordFromMapFlag(flag: MapFlagItem, dateBands: DateBand[]): RecordItem {
  const dateBand = dateBandForYear(flag.year, dateBands);
  return {
    record_id: flag.record_id,
    source_id: 0,
    query_id: null,
    figure_id: null,
    external_id: null,
    title: flag.title ?? `Mapped record ${flag.record_id}`,
    publication: null,
    author: null,
    date_published: flag.year ? String(flag.year) : null,
    year: flag.year,
    url: null,
    snippet: null,
    publicness_level: "summary-only",
    ingestion_status: "map_flag_only",
    source_name: "map flag index",
    source_type: flag.source_location_type ?? "map_flag",
    canonical_figure: flag.canonical_figure,
    cluster: null,
    tier: null,
    include_status: null,
    figure_humanoid_degree: null,
    ontology_default: null,
    involves_indigenous_knowledge: null,
    canonical_figure_guess: flag.canonical_figure,
    figure_name_as_printed: flag.canonical_figure,
    ontology_code: null,
    humanoid_degree_code: null,
    source_voice: "map flag metadata",
    genre: null,
    publicness_code: "summary_only",
    relevance_code: "map_flag_only",
    ethics_flag: null,
    coding_notes: "Map flag has no matching public record row in frontend-data records.",
    date_band: dateBand,
    location_summary: STATE_NAMES[flag.state_territory] ?? flag.state_territory,
    state_territory: flag.state_territory,
    location_precision_status: flag.display_precision,
    has_strict_map_point: true,
    map_latitude: flag.y,
    map_longitude: flag.x,
    map_place_name: flag.title,
    map_location_role: null,
    map_location_type: flag.source_location_type,
    map_geocode_source: null,
    map_verification_status: null,
    map_confidence: flag.confidence,
    map_evidence_text: null,
  };
}

function dateBandForYear(year: number | null, dateBands: DateBand[]) {
  if (year === null) {
    return "undated";
  }
  return dateBands.find((band) => year >= band.start && (band.end === null || year <= band.end))?.id ?? "undated";
}

function mapFlagCoordinates(flag: MapFlagItem, record: RecordItem) {
  if (Number.isFinite(flag.x) && Number.isFinite(flag.y)) {
    if (flag.x >= 110 && flag.x <= 160 && flag.y >= -45 && flag.y <= -8) {
      const projected = projectPoint(flag.y, flag.x);
      return { x: svgCoord(projected.x), y: svgCoord(projected.y) };
    }
    if (flag.x >= 0 && flag.x <= MAP_VIEWBOX.width && flag.y >= 0 && flag.y <= MAP_VIEWBOX.height) {
      return { x: svgCoord(flag.x), y: svgCoord(flag.y) };
    }
  }
  if (record.map_latitude != null && record.map_longitude != null) {
    const projected = projectPoint(record.map_latitude, record.map_longitude);
    return { x: svgCoord(projected.x), y: svgCoord(projected.y) };
  }
  return null;
}

function createFallbackMapFlags(records: RecordItem[]): MapFlagItem[] {
  return records.flatMap((record, index) => {
    if (!record.has_strict_map_point || record.map_latitude == null || record.map_longitude == null) {
      return [];
    }
    const projected = projectPoint(record.map_latitude, record.map_longitude);
    return [
      {
        flag_id: `record-${record.record_id}-${index}`,
        record_id: record.record_id,
        state_territory: record.state_territory ?? "AU",
        x: projected.x,
        y: projected.y,
        stem_dx: 0,
        stem_dy: 0,
        display_precision: record.location_precision_status ?? "strict",
        source_location_type: record.map_location_type ?? null,
        confidence: record.map_confidence ?? null,
        title: record.title,
        year: record.year,
        canonical_figure: record.canonical_figure_guess ?? record.canonical_figure,
      },
    ];
  });
}

function projectPoint(latitude: number, longitude: number) {
  const projected = projectLambertConformalConic(latitude, longitude);
  const jsonX =
    (projected.x - HICHARTS_AU_TRANSFORM.xoffset) *
      HICHARTS_AU_TRANSFORM.scale *
      HICHARTS_AU_TRANSFORM.jsonres +
    HICHARTS_AU_TRANSFORM.jsonmarginX;
  const jsonY =
    (projected.y - HICHARTS_AU_TRANSFORM.yoffset) *
      HICHARTS_AU_TRANSFORM.scale *
      HICHARTS_AU_TRANSFORM.jsonres +
    HICHARTS_AU_TRANSFORM.jsonmarginY;
  const x =
    SVG_BOUNDS.minX +
    ((jsonX - JSON_BOUNDS.minX) / (JSON_BOUNDS.maxX - JSON_BOUNDS.minX)) *
      (SVG_BOUNDS.maxX - SVG_BOUNDS.minX);
  const y =
    SVG_BOUNDS.minY +
    ((JSON_BOUNDS.maxY - jsonY) / (JSON_BOUNDS.maxY - JSON_BOUNDS.minY)) *
      (SVG_BOUNDS.maxY - SVG_BOUNDS.minY);

  return {
    x: Math.max(SVG_BOUNDS.minX + 4, Math.min(SVG_BOUNDS.maxX - 4, x)),
    y: Math.max(SVG_BOUNDS.minY + 4, Math.min(SVG_BOUNDS.maxY - 4, y)),
  };
}

function projectLambertConformalConic(latitude: number, longitude: number) {
  const deg = Math.PI / 180;
  const lat = latitude * deg;
  const lon = longitude * deg;
  const lat1 = LAMBERT_AU.lat1 * deg;
  const lat2 = LAMBERT_AU.lat2 * deg;
  const lat0 = LAMBERT_AU.lat0 * deg;
  const lon0 = LAMBERT_AU.lon0 * deg;
  const n =
    Math.log(Math.cos(lat1) / Math.cos(lat2)) /
    Math.log(Math.tan(Math.PI / 4 + lat2 / 2) / Math.tan(Math.PI / 4 + lat1 / 2));
  const f = (Math.cos(lat1) * Math.pow(Math.tan(Math.PI / 4 + lat1 / 2), n)) / n;
  const rho = (LAMBERT_AU.radius * f) / Math.pow(Math.tan(Math.PI / 4 + lat / 2), n);
  const rho0 = (LAMBERT_AU.radius * f) / Math.pow(Math.tan(Math.PI / 4 + lat0 / 2), n);
  const theta = n * (lon - lon0);

  return {
    x: rho * Math.sin(theta),
    y: rho0 - rho * Math.cos(theta),
  };
}

export function ArchiveTerminalRoute({ view }: { view: ViewMode }) {
  const [data, setData] = useState<FrontendData | null>(frontendDataCache);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadFrontendData()
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          setError(null);
        }
      })
      .catch((loadError: Error) => {
        if (!cancelled) {
          setError(loadError.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (data) {
    return <ArchiveTerminal data={data} view={view} />;
  }

  return (
    <ArchiveTerminalShell view={view}>
      <div className={`terminal-loading-state ${view === "map" ? "map-loading-state" : ""}`} role={error ? "alert" : "status"} aria-live="polite">
        <span>{error ? "DATA LOAD ERROR" : "LOADING PUBLIC ARCHIVE DATA"}</span>
        <b>{error ? error : FRONTEND_DATA_SCHEMA}</b>
        <small>{FRONTEND_DATA_URL}</small>
      </div>
    </ArchiveTerminalShell>
  );
}

export function ArchiveTerminal({ data, view }: { data: FrontendData; view: ViewMode }) {
  const derived = useMemo(() => createFrontendDerivedData(data), [data]);
  const [selectedRecord, setSelectedRecord] = useState<RecordItem | null>(null);
  const lastActiveElementRef = useRef<HTMLElement | SVGElement | null>(null);
  const overlayNavigation = selectedRecord ? recordNavigationContext(derived, selectedRecord) : null;

  const openRecord = useCallback((record: RecordItem) => {
    lastActiveElementRef.current =
      document.activeElement instanceof HTMLElement || document.activeElement instanceof SVGElement
        ? document.activeElement
        : null;
    setSelectedRecord(record);
  }, []);

  const closeRecord = useCallback(() => {
    setSelectedRecord(null);
    window.requestAnimationFrame(() => {
      lastActiveElementRef.current?.focus();
    });
  }, []);

  const showAdjacentRecord = useCallback((direction: 1 | -1) => {
    if (!overlayNavigation || overlayNavigation.records.length < 2) {
      return;
    }
    const nextIndex =
      (overlayNavigation.currentIndex + direction + overlayNavigation.records.length) % overlayNavigation.records.length;
    setSelectedRecord(overlayNavigation.records[nextIndex]);
  }, [overlayNavigation]);

  useEffect(() => {
    if (!selectedRecord) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeRecord();
      }
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        event.preventDefault();
        showAdjacentRecord(1);
      }
      if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        event.preventDefault();
        showAdjacentRecord(-1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeRecord, selectedRecord, showAdjacentRecord]);

  return (
    <ArchiveTerminalShell
      view={view}
      overlay={
        selectedRecord ? (
          <RecordCardOverlay
            record={selectedRecord}
            navigation={overlayNavigation}
            onClose={closeRecord}
            onNavigate={showAdjacentRecord}
          />
        ) : null
      }
    >
      {view === "map" ? <MapView data={data} derived={derived} onSelectRecord={openRecord} /> : null}
      {view === "density" ? <DensityView data={data} derived={derived} onSelectRecord={openRecord} /> : null}
      {view === "dashboard" ? <DashboardView data={data} derived={derived} onSelectRecord={openRecord} /> : null}
      {view === "source" ? <SourceView data={data} /> : null}
    </ArchiveTerminalShell>
  );
}

function ArchiveTerminalShell({
  view,
  children,
  overlay,
}: {
  view: ViewMode;
  children: React.ReactNode;
  overlay?: React.ReactNode;
}) {
  const nextView = getNextView(view);

  return (
    <main className="terminal-shell">
      <div className="noise-layer" aria-hidden="true" />
      <div className="terminal-stage">
        <section className={`view-area view-area-${view}`} aria-label={`${view} data view`}>
          {children}
        </section>
        <div className="terminal-footer-controls">
          <DisplayControls />

          <div className="external-control-dock" aria-label="Fixed external controls">
            <Link className="dock-button about-button" href="/about">
              About
            </Link>
            <Link
              className={view === "source" ? "dock-button source-button active" : "dock-button source-button"}
              href="/source"
              aria-current={view === "source" ? "page" : undefined}
            >
              Source
            </Link>
            <Link
              className="dock-button view-cycle-button"
              href={VIEW_PATHS[nextView]}
              aria-label={`Current view ${VIEW_LABELS[view]}; switch to ${VIEW_LABELS[nextView]}`}
              title={`Switch to ${VIEW_LABELS[nextView]}`}
            >
              <span className="view-label-current">{view === "source" ? VIEW_LABELS[nextView] : VIEW_LABELS[view]}</span>
              <span className="view-label-next">{view === "source" ? null : VIEW_LABELS[nextView]}</span>
            </Link>
          </div>
        </div>
      </div>
      {overlay}
    </main>
  );
}

function getNextView(view: ViewMode) {
  const index = VIEW_SEQUENCE.indexOf(view);
  if (index === -1) {
    return "dashboard";
  }
  return VIEW_SEQUENCE[(index + 1) % VIEW_SEQUENCE.length];
}

function flagTargetFromEvent(event: React.SyntheticEvent<SVGGElement>) {
  const target = event.target;
  if (!(target instanceof Element)) {
    return null;
  }
  return target.closest("[data-record-id]");
}

function useMapFlagGrowth(layerRef: RefObject<SVGGElement | null>, flagSignature: string) {
  const reducedMotion = usePrefersReducedMotion();
  const timelineRef = useRef<Timeline | null>(null);

  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) {
      return;
    }
    const glyphs = Array.from(layer.querySelectorAll<SVGCircleElement>(".record-flag-dot"));
    timelineRef.current?.cancel();
    timelineRef.current = null;

    if (!glyphs.length || reducedMotion) {
      glyphs.forEach((glyph) => {
        glyph.style.opacity = "1";
        glyph.style.transform = "scale(1)";
      });
      layer.classList.add("flags-grown");
      return;
    }

    layer.classList.remove("flags-grown");
    glyphs.forEach((glyph) => {
      glyph.style.opacity = "0";
      glyph.style.transform = "scale(1)";
    });

    const bucketGroups = new Map<string, SVGCircleElement[]>();
    for (const glyph of glyphs) {
      const bucket = glyph.dataset.growthBucket ?? "0";
      const group = bucketGroups.get(bucket) ?? [];
      group.push(glyph);
      bucketGroups.set(bucket, group);
    }

    const finishGrowth = () => {
      glyphs.forEach((glyph) => {
        glyph.style.opacity = "1";
        glyph.style.transform = "scale(1)";
      });
      layer.classList.remove("flags-growing");
      layer.classList.add("flags-grown");
    };

    layer.classList.add("flags-growing");
    const timeline = createTimeline({
      defaults: {
        ease: "linear",
        composition: "replace",
      },
      onComplete: finishGrowth,
    });

    let position = 260;
    const chunkSize = 30;
    const chunkInterval = 42;
    const bucketGap = 120;

    for (let bucket = 0; bucket < MAP_FLAG_GROWTH_BUCKETS.length; bucket += 1) {
      const bucketGlyphs = [...(bucketGroups.get(String(bucket)) ?? [])].sort((a, b) => (
        Number(a.dataset.growthOrder ?? 0) - Number(b.dataset.growthOrder ?? 0)
      ));
      if (!bucketGlyphs.length) {
        continue;
      }
      for (let index = 0; index < bucketGlyphs.length; index += chunkSize) {
        timeline.add(bucketGlyphs.slice(index, index + chunkSize), {
          opacity: 1,
          duration: 1,
        }, position);
        position += chunkInterval;
      }
      position += bucketGap;
    }

    timeline.add(glyphs, { opacity: 1, scale: 1, duration: 1 }, position);
    timelineRef.current = timeline;

    return () => {
      layer.classList.remove("flags-growing");
      timeline.cancel();
    };
  }, [flagSignature, layerRef, reducedMotion]);

  useEffect(() => {
    return () => {
      timelineRef.current?.cancel();
      timelineRef.current = null;
    };
  }, []);
}

function useMapAmbientMotion(rootRef: RefObject<HTMLElement | null>) {
  const reducedMotion = usePrefersReducedMotion();
  const timelineRef = useRef<Timeline | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || reducedMotion) {
      return;
    }

    const start = () => {
      timelineRef.current?.cancel();
      const timeline = createTimeline({
        loop: true,
        alternate: true,
        defaults: {
          ease: "inOutSine",
          duration: 4600,
          composition: "replace",
        },
      });
      addIfTargets(timeline, root.querySelectorAll(".map-readout-led, .map-source-block-indicator"), {
        opacity: [0.36, 0.66],
        scale: [1, 1.018],
      }, 0);
      addIfTargets(timeline, root.querySelectorAll(".map-source-legend-row svg"), {
        opacity: [0.42, 0.68],
        scale: [1, 1.014],
      }, 520);
      timelineRef.current = timeline;
    };

    const stop = () => {
      timelineRef.current?.cancel();
      timelineRef.current = null;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        start();
      } else {
        stop();
      }
    };

    start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stop();
    };
  }, [reducedMotion, rootRef]);
}

function MapView({
  data,
  derived,
  onSelectRecord,
}: {
  data: FrontendData;
  derived: FrontendDerivedData;
  onSelectRecord: (record: RecordItem) => void;
}) {
  const mapRootRef = useRef<HTMLDivElement | null>(null);
  const mapLayerRef = useRef<SVGGElement | null>(null);
  const [hoverState, setHoverState] = useState<string | null>(null);
  const [hoverRecordId, setHoverRecordId] = useState<number | null>(null);
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null);
  const stateCounts = data.summary.corpus_state_counts ?? data.summary.state_record_counts;
  const mapFlags = derived.mapFlags;
  const preciseStateCounts = derived.mappedStateCounts;
  const activeState = hoverState ? STATE_NAMES[hoverState] : "Australia";
  const activeCount = hoverState ? preciseStateCounts[hoverState] ?? 0 : mapFlags.length;
  const flagSignature = `${mapFlags.length}:${mapFlags[0]?.flag_id ?? "none"}:${mapFlags.at(-1)?.flag_id ?? "none"}`;
  const sourceLegend = useMemo(() => buildMapSourceLegend(mapFlags), [mapFlags]);

  useMapFlagGrowth(mapLayerRef, flagSignature);
  useMapAmbientMotion(mapRootRef);

  const hoverFlagFromEvent = useCallback((event: React.SyntheticEvent<SVGGElement>) => {
    const element = flagTargetFromEvent(event);
    const recordId = Number(element?.getAttribute("data-record-id"));
    const flag = Number.isFinite(recordId) ? derived.mapFlagRecordLookup.get(recordId) : null;
    if (!flag) {
      return;
    }
    setHoverRecordId(flag.record_id);
    setHoverState(flag.state_territory);
  }, [derived.mapFlagRecordLookup]);

  const clearFlagHover = useCallback(() => {
    setHoverRecordId(null);
    setHoverState(null);
  }, []);

  const clearFlagFocus = useCallback((event: React.FocusEvent<SVGGElement>) => {
    if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) {
      return;
    }
    clearFlagHover();
  }, [clearFlagHover]);

  const selectFlagFromEvent = useCallback((event: React.SyntheticEvent<SVGGElement>) => {
    const element = flagTargetFromEvent(event);
    const recordId = Number(element?.getAttribute("data-record-id"));
    const flag = Number.isFinite(recordId) ? derived.mapFlagRecordLookup.get(recordId) : null;
    if (flag) {
      setSelectedRecordId(flag.record_id);
      onSelectRecord(flag.record);
    }
  }, [derived.mapFlagRecordLookup, onSelectRecord]);

  const handleFlagKeyDown = useCallback((event: React.KeyboardEvent<SVGGElement>) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    const element = flagTargetFromEvent(event);
    if (!element) {
      return;
    }
    event.preventDefault();
    selectFlagFromEvent(event);
  }, [selectFlagFromEvent]);

  return (
    <div className="map-view" ref={mapRootRef}>
      <div className="map-source-block" aria-label="Map boundary and terrain source">
        <i className="map-source-block-indicator" aria-hidden="true" />
        <span>BOUNDARY: {MAP_BOUNDARY_SOURCE.name}</span>
        <span>TERRAIN: {TERRAIN_TILES.length} LANDFORM CUES / STATE-CLIPPED</span>
      </div>
      <div className="map-canvas">
        <svg
          className="australia-map"
          viewBox={`0 0 ${MAP_VIEWBOX.width} ${MAP_VIEWBOX.height}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Public signal map of Australia by state and territory"
        >
          <MapPatternDefs />
          <TerrainSurfaceLayer hoverState={hoverState} />
          {STATE_SHAPES.map((state) => {
            const count = stateCounts[state.code] ?? 0;
            const intensity = count > 1 ? "hot" : count === 1 ? "warm" : "cold";
            return (
              <g key={state.code}>
                <path
                  className={`state-shape ${hoverState === state.code ? "hovered" : ""} ${intensity}`}
                  d={state.d}
                  onMouseEnter={() => setHoverState(state.code)}
                  onPointerEnter={() => setHoverState(state.code)}
                  onMouseLeave={() => setHoverState(null)}
                  onPointerLeave={() => setHoverState(null)}
                />
              </g>
            );
          })}
          <path className="coast-outline" d={STATE_SHAPES.map((state) => state.d).join(" ")} />
          <g
            ref={mapLayerRef}
            className={`record-flag-layer ${hoverState ? "has-state-hover" : ""} ${hoverRecordId ? "has-hover" : ""}`}
            aria-label="Strict geocoded public record flags"
            onPointerOver={hoverFlagFromEvent}
            onPointerLeave={clearFlagHover}
            onFocus={hoverFlagFromEvent}
            onBlur={clearFlagFocus}
            onClick={selectFlagFromEvent}
            onKeyDown={handleFlagKeyDown}
          >
            {mapFlags.map((flag) => (
              <MapFlagMarker
                key={flag.flag_id}
                flag={flag}
                active={hoverRecordId === flag.record_id || selectedRecordId === flag.record_id}
                stateLinked={hoverState === flag.state_territory}
              />
            ))}
          </g>
          <g className="state-label-layer" aria-hidden="true">
            {STATE_SHAPES.map((state) => {
              const label = STATE_LABEL_OVERRIDES[state.code as keyof typeof STATE_NAMES] ?? state.label;
              return (
                <text
                  key={`label-${state.code}`}
                  className={`state-label state-label-${state.code.toLowerCase()}`}
                  x={label[0]}
                  y={label[1]}
                >
                  {state.code}
                </text>
              );
            })}
          </g>
          <TerrainLegend />
        </svg>
      </div>

      <aside className="map-readout">
        <div className="readout-block">
          <i className="map-readout-led" aria-hidden="true" />
          <span className="tiny-label">REGION</span>
          <strong>{activeState}</strong>
          <span className="readout-number">{mapCount(activeCount)}</span>
          <span className="readout-tail">mapped records</span>
        </div>
        <div className="readout-grid">
          {Object.entries(STATE_NAMES).map(([code]) => (
            <button
              type="button"
              className={hoverState === code ? "state-mini active" : "state-mini"}
              key={code}
              onMouseEnter={() => setHoverState(code)}
              onPointerEnter={() => setHoverState(code)}
              onMouseLeave={() => setHoverState(null)}
              onPointerLeave={() => setHoverState(null)}
              onFocus={() => setHoverState(code)}
              onBlur={() => setHoverState(null)}
            >
              <span>{code}</span>
              <b>{mapCount(preciseStateCounts[code] ?? 0)}</b>
            </button>
          ))}
        </div>
        <div className="map-health-note">
          <span>MAPPED RECORDS</span>
          <b>{mapCount(mapFlags.length)}</b>
          <small>{mapCount(mapFlags.length)} mapped / {mapCount(data.summary.record_count)} public records</small>
          <em>one flag per verified public record</em>
        </div>
        <MapSourceLegend items={sourceLegend} />
      </aside>
    </div>
  );
}

const MapFlagMarker = memo(function MapFlagMarker({
  flag,
  active,
  stateLinked,
}: {
  flag: MapFlagRenderItem;
  active: boolean;
  stateLinked: boolean;
}) {
  const className = ["record-flag", "precise", flag.toneClass, active ? "active" : "", stateLinked ? "state-linked" : ""]
    .filter(Boolean)
    .join(" ");
  const label = flag.title || flag.canonical_figure || `Record ${flag.record_id}`;
  const dotRadius = active ? 5.2 : stateLinked ? 3.8 : 3.6;

  return (
    <g
      className={className}
      data-record-id={flag.record_id}
      role="button"
      tabIndex={0}
      aria-label={`Open mapped record ${label}`}
    >
      <circle className="record-flag-hit" cx={flag.displayX} cy={flag.displayY} r="10" />
      <circle
        className="record-flag-dot"
        cx={flag.displayX}
        cy={flag.displayY}
        r={dotRadius}
        data-growth-bucket={flag.growthBucket}
        data-growth-order={flag.growthOrder}
      />
      {active ? <circle className="record-flag-active-ring" cx={flag.displayX} cy={flag.displayY} r="8.1" /> : null}
      {active ? (
        <text className="record-flag-label" x={Math.min(flag.displayX + 12, MAP_VIEWBOX.width - 150)} y={Math.max(flag.displayY - 10, 26)}>
          {flag.year ?? "--"} / {truncate(flag.canonical_figure ?? label, 24)}
        </text>
      ) : null}
    </g>
  );
}, (prev, next) => (
  prev.flag === next.flag &&
  prev.active === next.active &&
  prev.stateLinked === next.stateLinked
));

function MapSourceLegend({ items }: { items: MapSourceLegendItem[] }) {
  return (
    <div className="map-source-legend" aria-label="Flag source categories">
      <span>FLAG SOURCE</span>
      {items.map((item) => (
        <div className={`map-source-legend-row record-flag ${item.className}`} key={item.id}>
          <svg viewBox="0 0 18 18" aria-hidden="true">
            <circle className="record-flag-dot legend-dot" cx="9" cy="9" r="3.3" />
          </svg>
          <b>{item.label}</b>
          <small>{mapCount(item.count)}</small>
        </div>
      ))}
    </div>
  );
}

function TerrainLegend() {
  const frameWidth = 242;
  const frameHeight = 84;
  const inset = 14;
  const columnGap = 124;

  return (
    <g className="terrain-legend" transform={`translate(8 ${MAP_VIEWBOX.height - 118})`} aria-label="Terrain tile key">
      <rect className="terrain-legend-back" x="0" y="0" width={frameWidth} height={frameHeight} />
      {TERRAIN_KINDS.map((kind, index) => {
        const column = index > 3 ? 1 : 0;
        const row = column ? index - 4 : index;
        const x = inset + column * columnGap;
        const y = 20 + row * 17;
        return (
          <g key={kind} transform={`translate(${x} ${y})`}>
            <text className={`terrain-legend-symbol terrain-pattern-${kind}`} x="0" y="0">
              {TERRAIN_SYMBOLS[kind]}
              {TERRAIN_SYMBOLS[kind]}
            </text>
            <text className="terrain-legend-label" x="24" y="0">
              {TERRAIN_LABELS[kind]}
            </text>
          </g>
        );
      })}
    </g>
  );
}

function MapPatternDefs() {
  return (
    <defs>
      {TERRAIN_KINDS.map((kind, index) => (
        <pattern
          key={kind}
          id={`terrain-pattern-${kind}`}
          width={kind === "plain" ? 36 : 42}
          height={kind === "plain" ? 30 : 38}
          patternUnits="userSpaceOnUse"
          patternTransform={`translate(${index * 7} ${index * 5})`}
        >
          <text className={`terrain-pattern-symbol terrain-pattern-${kind}`} x="5" y="13">
            {TERRAIN_SYMBOLS[kind]}
          </text>
          <text className={`terrain-pattern-symbol terrain-pattern-${kind}`} x="22" y="28">
            {TERRAIN_SYMBOLS[kind]}
          </text>
          <text className={`terrain-pattern-symbol terrain-pattern-${kind}`} x="31" y="11">
            {TERRAIN_SYMBOLS[kind]}
          </text>
        </pattern>
      ))}
      {STATE_SHAPES.map((state) => (
        <clipPath key={state.code} id={`clip-state-${state.code}`}>
          <path d={state.d} />
        </clipPath>
      ))}
    </defs>
  );
}

function TerrainSurfaceLayer({ hoverState }: { hoverState: string | null }) {
  return (
    <g className="terrain-surface-layer" aria-label="State-clipped landform texture layer">
      {STATE_SHAPES.flatMap((state) => {
        const kinds = STATE_TERRAIN_KINDS[state.code] ?? ["plain"];
        return kinds.slice(0, 3).map((kind, index) => (
          <rect
            key={`${state.code}-${kind}`}
            className={`terrain-surface terrain-surface-${kind} ${
              hoverState === state.code ? "emphasized" : hoverState ? "dimmed" : "idle"
            }`}
            style={
              {
                "--terrain-idle": String(Math.max(0.08, 0.22 - index * 0.05)),
                "--terrain-active": String(Math.max(0.32, 0.72 - index * 0.1)),
              } as CSSProperties
            }
            clipPath={`url(#clip-state-${state.code})`}
            x="0"
            y="0"
            width={MAP_VIEWBOX.width}
            height={MAP_VIEWBOX.height}
            fill={`url(#terrain-pattern-${kind})`}
          />
        ));
      })}
    </g>
  );
}

function DensityView({
  data,
  derived,
  onSelectRecord,
}: {
  data: FrontendData;
  derived: FrontendDerivedData;
  onSelectRecord: (record: RecordItem) => void;
}) {
  const [analysisSchemeId, setAnalysisSchemeId] = useState<DensityPeriodSchemeId>("historical_context");
  const [analysisTab, setAnalysisTab] = useState<DensityAnalysisTab>("temporal_narrative");
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | null>(null);
  const periodSchemes = useMemo(() => buildDensityPeriodSchemes(data.records), [data.records]);
  const overviewScheme = periodSchemes.find((scheme) => scheme.id === "historical_context") ?? periodSchemes[0];
  const analysisScheme = periodSchemes.find((scheme) => scheme.id === analysisSchemeId) ?? overviewScheme;
  const overviewSummaries = useMemo(
    () => buildDensityPeriodSummaries(overviewScheme, data.records, derived.mapFlags),
    [data.records, derived.mapFlags, overviewScheme],
  );
  const analysisSummaries = useMemo(
    () => buildDensityPeriodSummaries(analysisScheme, data.records, derived.mapFlags),
    [analysisScheme, data.records, derived.mapFlags],
  );
  const selectedPeriod =
    overviewSummaries.find((summary) => summary.period.id === selectedPeriodId) ??
    [...overviewSummaries].sort((a, b) => b.records.length - a.records.length)[0] ??
    null;
  const narrativeCards = useMemo(() => buildDensityNarrativeCards(data.records, derived.mapFlags), [data.records, derived.mapFlags]);

  return (
    <div className="density-view">
      <header className="density-header">
        <span>DENSITY FIELD / PUBLIC-TEXT PERIOD LENSES</span>
        <b>
          {data.summary.earliest_year}-{data.summary.latest_year} / {data.summary.record_count} PUBLIC / {data.summary.mapped_record_count} MAPPED
        </b>
      </header>
      <div className="density-field-stack">
        <section className="density-field density-field-overview" id="density-field-overview" aria-label="Density overview">
          <div className="density-field-heading">
            <span>FIELD 01</span>
            <b>DENSITY OVERVIEW</b>
            <p>Default periods are historical/public-text context bands. They help interpret source and publication environments; they do not imply causation.</p>
          </div>
          <div className="density-period-row">
            {overviewSummaries.map((summary, index) => (
              <DensityPeriodCard
                key={summary.period.id}
                summary={summary}
                index={index}
                maxRecords={Math.max(...overviewSummaries.map((item) => item.records.length), 1)}
                selected={selectedPeriod?.period.id === summary.period.id}
                onSelect={() => setSelectedPeriodId(summary.period.id)}
                onSelectRecord={onSelectRecord}
              />
            ))}
          </div>
          <div className="density-overview-grid">
            <DensityNarrativeCards cards={narrativeCards} onSelectRecord={onSelectRecord} />
            <DensitySelectedPeriodSummary summary={selectedPeriod} undatedCount={derived.undatedRecordCount} />
          </div>
        </section>

        <section className="density-field density-field-method" id="density-field-method" aria-label="Period method comparator">
          <div className="density-field-heading">
            <span>FIELD 02</span>
            <b>PERIOD METHOD COMPARATOR</b>
            <p>The archive can be sliced in several defensible ways. Historical context bands preserve publication and public-text context. Equal-duration bands test uneven period widths. Equal-record bands test composition without letting one dense period dominate the display.</p>
          </div>
          <DensityMethodComparator schemes={periodSchemes} records={data.records} mapFlags={derived.mapFlags} />
          <p className="density-method-note">
            Period lenses are interpretive display tools. They organise public records for reading; they do not establish real-world frequency or causation. Equal-record bins are a comparison tool and can hide real temporal concentration.
          </p>
        </section>

        <section className="density-field density-field-analysis" id="density-field-analysis" aria-label="Analytical field">
          <div className="density-field-heading density-analysis-heading">
            <span>FIELD 03</span>
            <b>ANALYTICAL FIELD</b>
            <p>Charts use the selected period lens and show archive record density, source coverage, and map eligibility patterns.</p>
          </div>
          <DensityAnalysisControls selectedSchemeId={analysisScheme.id} selectedTab={analysisTab} onSchemeChange={setAnalysisSchemeId} onTabChange={setAnalysisTab} />
          <DensityAnalysisField tab={analysisTab} scheme={analysisScheme} summaries={analysisSummaries} records={data.records} mapFlags={derived.mapFlags} />
        </section>
      </div>
    </div>
  );
}

function DensityPeriodCard({
  summary,
  index,
  maxRecords,
  selected,
  onSelect,
  onSelectRecord,
}: {
  summary: DensityPeriodSummary;
  index: number;
  maxRecords: number;
  selected: boolean;
  onSelect: () => void;
  onSelectRecord: (record: RecordItem) => void;
}) {
  const recordLevel = Math.ceil((summary.records.length / maxRecords) * 28);
  const char = DENSITY_CHARS[Math.min(DENSITY_CHARS.length - 1, index)];
  const mappedShare = formatPercent(summary.mappedCount, summary.records.length);
  return (
    <section className={`density-band density-period-card${selected ? " selected" : ""}`}>
      <div className="density-matrix" aria-hidden="true">
        {Array.from({ length: 28 }).map((_, cellIndex) => (
          <span key={cellIndex} className={cellIndex < recordLevel ? "matrix-cell lit" : "matrix-cell"}>
            {cellIndex < recordLevel ? char : "."}
          </span>
        ))}
      </div>
      <div className="band-meta">
        <span>{summary.period.shortLabel}</span>
        <strong>{summary.period.label}</strong>
        <b>{numberFormat(summary.records.length)}</b>
        <small style={{ "--query-level": `${Math.max(5, Math.round((summary.mappedCount / Math.max(1, summary.records.length)) * 100))}%` } as CSSProperties}>
          mapped {summary.mappedCount} / {mappedShare}
        </small>
      </div>
      <dl className="density-period-metrics">
        <div>
          <dt>Narrative</dt>
          <dd>{summary.topNarrative}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{summary.topSourceFamily}</dd>
        </div>
      </dl>
      <div className="density-card-actions">
        <button type="button" onClick={onSelect} aria-pressed={selected}>
          inspect
        </button>
        <button
          type="button"
          disabled={!summary.firstRecord}
          onClick={() => {
            if (summary.firstRecord) {
              onSelectRecord(summary.firstRecord);
            }
          }}
        >
          sample
        </button>
      </div>
    </section>
  );
}

function DensityNarrativeCards({ cards, onSelectRecord }: { cards: DensityNarrativeCard[]; onSelectRecord: (record: RecordItem) => void }) {
  const [selectedLabel, setSelectedLabel] = useState<string | null>(cards[0]?.label ?? null);
  const selectedCard = cards.find((card) => card.label === selectedLabel) ?? cards[0] ?? null;

  return (
    <section className="density-narrative-panel">
      <div className="density-panel-heading">
        <span>FIGURE / NARRATIVE SIGNAL</span>
        <b>PUBLIC-TEXT FAMILIES</b>
      </div>
      <div className="density-narrative-grid">
        {cards.slice(0, 6).map((card) => (
          <article className="density-narrative-card" key={card.label}>
            <i aria-hidden="true">{card.glyph}</i>
            <div>
              <span>{card.label}</span>
              <b>{numberFormat(card.records.length)} records / {numberFormat(card.mappedCount)} mapped</b>
              <small>{card.dateSpan} / {card.topSourceFamily}</small>
            </div>
            <p>{card.description}</p>
            <em>{card.sensitivityNote}</em>
            <button
              type="button"
              aria-pressed={selectedCard?.label === card.label}
              onClick={() => setSelectedLabel(card.label)}
            >
              inspect
            </button>
          </article>
        ))}
      </div>
      {selectedCard ? (
        <aside className="density-figure-inspector">
          <div>
            <span>FIGURE-CARD INSPECTOR</span>
            <b>{selectedCard.label}</b>
          </div>
          <p>{selectedCard.description}</p>
          <dl>
            <div>
              <dt>Records</dt>
              <dd>{numberFormat(selectedCard.records.length)}</dd>
            </div>
            <div>
              <dt>Mapped</dt>
              <dd>{numberFormat(selectedCard.mappedCount)}</dd>
            </div>
            <div>
              <dt>Date span</dt>
              <dd>{selectedCard.dateSpan}</dd>
            </div>
            <div>
              <dt>Top source</dt>
              <dd>{selectedCard.topSourceFamily}</dd>
            </div>
          </dl>
          <em>{selectedCard.sensitivityNote}</em>
          <button
            type="button"
            disabled={!selectedCard.records[0]}
            onClick={() => {
              if (selectedCard.records[0]) {
                onSelectRecord(selectedCard.records[0]);
              }
            }}
          >
            sample record
          </button>
        </aside>
      ) : null}
    </section>
  );
}

function DensitySelectedPeriodSummary({ summary, undatedCount }: { summary: DensityPeriodSummary | null; undatedCount: number }) {
  return (
    <section className="density-selected-panel">
      <div className="density-panel-heading">
        <span>SELECTED PERIOD SUMMARY</span>
        <b>{summary ? summary.period.shortLabel : "No period selected"}</b>
      </div>
      {summary ? (
        <div className="density-selected-grid">
          <div>
            <span>YEARS</span>
            <b>{summary.period.label}</b>
          </div>
          <div>
            <span>PUBLIC RECORDS</span>
            <b>{numberFormat(summary.records.length)}</b>
          </div>
          <div>
            <span>MAPPED</span>
            <b>{numberFormat(summary.mappedCount)} / {formatPercent(summary.mappedCount, summary.records.length)}</b>
          </div>
          <div>
            <span>TOP NARRATIVE</span>
            <b>{summary.topNarrative}</b>
          </div>
          <div>
            <span>TOP SOURCE</span>
            <b>{summary.topSourceFamily}</b>
          </div>
        </div>
      ) : null}
      <p>{summary?.period.anchorNote ?? "Select a period card to inspect the contextual band."}</p>
      <small>UNDATED: {numberFormat(undatedCount)} public records. Undated records are not forced into a false period.</small>
    </section>
  );
}

function DensityMethodComparator({
  schemes,
  records,
  mapFlags,
}: {
  schemes: DensityPeriodScheme[];
  records: readonly RecordItem[];
  mapFlags: readonly MapFlagRenderItem[];
}) {
  const rows = schemes.map((scheme) => ({
    scheme,
    summaries: buildDensityPeriodSummaries(scheme, records, mapFlags),
  }));
  const max = Math.max(...rows.flatMap((row) => row.summaries.map((summary) => summary.records.length)), 1);

  return (
    <div className="density-method-comparator">
      {rows.map(({ scheme, summaries }) => (
        <section className="density-method-row" key={scheme.id}>
          <header>
            <span>{scheme.label.toUpperCase()}</span>
            <small>{scheme.description}</small>
          </header>
          <div className="density-method-blocks">
            {summaries.map((summary) => {
              const intensity = summary.records.length / max;
              return (
                <div className="density-method-block" key={summary.period.id} style={{ "--period-intensity": String(0.12 + intensity * 0.78) } as CSSProperties}>
                  <b>{summary.period.shortLabel}</b>
                  <span>{summary.period.label}</span>
                  <i style={{ "--mapped-share": `${Math.max(3, (summary.mappedCount / Math.max(1, summary.records.length)) * 100)}%` } as CSSProperties} />
                  <em>{numberFormat(summary.records.length)}</em>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

function DensityAnalysisControls({
  selectedSchemeId,
  selectedTab,
  onSchemeChange,
  onTabChange,
}: {
  selectedSchemeId: DensityPeriodSchemeId;
  selectedTab: DensityAnalysisTab;
  onSchemeChange: (id: DensityPeriodSchemeId) => void;
  onTabChange: (id: DensityAnalysisTab) => void;
}) {
  const schemes: Array<{ id: DensityPeriodSchemeId; label: string }> = [
    { id: "historical_context", label: "Historical Context" },
    { id: "equal_duration", label: "Equal Duration" },
    { id: "equal_record_count", label: "Equal Record Count" },
  ];
  const tabs: Array<{ id: DensityAnalysisTab; label: string }> = [
    { id: "temporal_narrative", label: "TEMPORAL × NARRATIVE" },
    { id: "source_bias", label: "SOURCE BIAS" },
    { id: "map_coverage", label: "MAP COVERAGE" },
    { id: "regional_profile", label: "REGIONAL PROFILE" },
  ];

  return (
    <div className="density-analysis-controls">
      <div>
        <span>PERIOD LENS</span>
        {schemes.map((scheme) => (
          <button key={scheme.id} type="button" className={selectedSchemeId === scheme.id ? "active" : ""} onClick={() => onSchemeChange(scheme.id)}>
            {scheme.label}
          </button>
        ))}
      </div>
      <div>
        <span>ANALYSIS</span>
        {tabs.map((tab) => (
          <button key={tab.id} type="button" className={selectedTab === tab.id ? "active" : ""} onClick={() => onTabChange(tab.id)}>
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function DensityAnalysisField({
  tab,
  scheme,
  summaries,
  records,
  mapFlags,
}: {
  tab: DensityAnalysisTab;
  scheme: DensityPeriodScheme;
  summaries: DensityPeriodSummary[];
  records: readonly RecordItem[];
  mapFlags: readonly MapFlagRenderItem[];
}) {
  if (tab === "source_bias") {
    return (
      <DensityAnalysisMatrix
        title="SOURCE FAMILY x PERIOD"
        note="Dense periods may reflect source availability or collection history rather than more narratives in the world."
        rows={SOURCE_FAMILIES.map((family) => ({
          label: family.label,
          values: summaries.map((summary) => summary.records.filter((record) => sourceFamilyFor(record.source_type).id === family.id).length),
        }))}
        periods={scheme.periods}
      />
    );
  }
  if (tab === "map_coverage") {
    return <DensityMapCoverageChart summaries={summaries} />;
  }
  if (tab === "regional_profile") {
    return <DensityRegionalProfile records={records} mapFlags={mapFlags} periods={scheme.periods} />;
  }
  return (
    <DensityAnalysisMatrix
      title="NARRATIVE FAMILY x PERIOD"
      note="This view shows which narrative families are represented in each period. It shows archive record density, not real-world frequency."
      rows={NARRATIVE_MATRIX_LABELS.map((label) => ({
        label,
        values: summaries.map((summary) => summary.records.filter((record) => displayNarrativeGroupLabel(record) === label).length),
      }))}
      periods={scheme.periods}
    />
  );
}

function DensityAnalysisMatrix({
  title,
  note,
  rows,
  periods,
}: {
  title: string;
  note: string;
  rows: Array<{ label: string; values: number[] }>;
  periods: readonly DensityPeriod[];
}) {
  const max = Math.max(...rows.flatMap((row) => row.values), 1);

  return (
    <section className="density-analysis-panel">
      <div className="density-panel-heading">
        <span>{title}</span>
        <b>{periods.map((period) => period.shortLabel).join(" / ")}</b>
      </div>
      <div className="density-analysis-matrix" style={{ "--matrix-cols": periods.length } as CSSProperties}>
        <span />
        {periods.map((period) => <b key={period.id}>{period.shortLabel}</b>)}
        {rows.map((row) => (
          <div className="density-analysis-row" key={row.label}>
            <span>{row.label}</span>
            {row.values.map((value, index) => (
              <i key={`${row.label}-${periods[index]?.id}`} style={{ "--heat": String(value / max) } as CSSProperties} title={`${row.label}, ${periods[index]?.label}: ${numberFormat(value)}`}>
                {value > 0 ? numberFormat(value) : ""}
              </i>
            ))}
          </div>
        ))}
      </div>
      <p>{note}</p>
    </section>
  );
}

function DensityMapCoverageChart({ summaries }: { summaries: DensityPeriodSummary[] }) {
  const max = Math.max(...summaries.map((summary) => summary.records.length), 1);
  return (
    <section className="density-analysis-panel density-map-coverage">
      <div className="density-panel-heading">
        <span>MAPPED / UNMAPPED BY PERIOD</span>
        <b>MAP ELIGIBILITY RATIO</b>
      </div>
      <div className="density-coverage-bars">
        {summaries.map((summary) => {
          const unmapped = Math.max(0, summary.records.length - summary.mappedCount);
          return (
            <div key={summary.period.id} className="density-coverage-row">
              <span>{summary.period.shortLabel}</span>
              <i>
                <b style={{ "--bar-width": `${Math.max(2, (summary.mappedCount / max) * 100)}%` } as CSSProperties} />
                <em style={{ "--bar-width": `${Math.max(2, (unmapped / max) * 100)}%` } as CSSProperties} />
              </i>
              <strong>{numberFormat(summary.mappedCount)} / {formatPercent(summary.mappedCount, summary.records.length)}</strong>
            </div>
          );
        })}
      </div>
      <p>A record can be source-grounded but remain unmapped if it lacks a verified display location or should remain broad, sensitive, or summary-only.</p>
    </section>
  );
}

function DensityRegionalProfile({
  records,
  mapFlags,
  periods,
}: {
  records: readonly RecordItem[];
  mapFlags: readonly MapFlagRenderItem[];
  periods: readonly DensityPeriod[];
}) {
  const rows = DASHBOARD_STATE_ORDER.map((state) => ({
    label: state,
    values: periods.map((period) => records.filter((record) => record.state_territory === state && periodContainsYear(period, record.year)).length),
    mapped: periods.map((period) => mapFlags.filter((flag) => flag.state_territory === state && periodContainsYear(period, flag.record.year)).length),
  }));
  const max = Math.max(...rows.flatMap((row) => row.values), 1);
  return (
    <section className="density-analysis-panel">
      <div className="density-panel-heading">
        <span>JURISDICTION x PERIOD</span>
        <b>PUBLIC RECORDS / MAPPED SIGNAL</b>
      </div>
      <div className="density-regional-grid" style={{ "--matrix-cols": periods.length } as CSSProperties}>
        <span />
        {periods.map((period) => <b key={period.id}>{period.shortLabel}</b>)}
        {rows.map((row) => (
          <div className="density-regional-row" key={row.label}>
            <span>{row.label}</span>
            {row.values.map((value, index) => (
              <i key={`${row.label}-${periods[index]?.id}`} style={{ "--heat": String(value / max), "--mapped-share": `${Math.max(3, (row.mapped[index] / Math.max(1, value)) * 100)}%` } as CSSProperties}>
                {value ? numberFormat(value) : ""}
              </i>
            ))}
          </div>
        ))}
      </div>
      <p>Regional density reflects source coverage and map eligibility. It is not a verified distribution of supernatural beings or events.</p>
    </section>
  );
}

function buildDensityPeriodSummaries(
  scheme: DensityPeriodScheme,
  records: readonly RecordItem[],
  mapFlags: readonly MapFlagRenderItem[],
): DensityPeriodSummary[] {
  return scheme.periods.map((period) => {
    const periodRecords = records.filter((record) => periodContainsYear(period, record.year));
    const mappedCount = mapFlags.filter((flag) => periodContainsYear(period, flag.record.year)).length;
    return {
      period,
      records: periodRecords,
      mappedCount,
      topNarrative: topLabel(periodRecords, (record) => displayNarrativeGroupLabel(record)),
      topSourceFamily: topLabel(periodRecords, (record) => sourceFamilyFor(record.source_type).label),
      firstRecord: [...periodRecords].sort(compareRecordsByDate)[0] ?? null,
    };
  });
}

function buildDensityNarrativeCards(records: readonly RecordItem[], mapFlags: readonly MapFlagRenderItem[]): DensityNarrativeCard[] {
  const mappedIds = new Set(mapFlags.map((flag) => flag.record_id));
  const descriptions: Record<string, string> = {
    "Hairy humanoid reports": "Reports and retellings using hairy-human or wild-person language in public sources.",
    "Spirit-person narratives": "Public records involving spirit-person or culturally specific narrative language, handled as source-context records.",
    "Ghost / apparition records": "Apparition and ghost records where the public text presents a humanoid or person-like figure.",
    "Traditional narratives": "Public-source traditional narrative records requiring careful terminology and contextual reading.",
    "Retellings and adaptations": "Later adaptations, summaries, or retellings that show circulation rather than primary evidence.",
    "Giant / ogre narratives": "Giant, ogre, or large humanoid narrative records in public textual circulation.",
    "Local legends": "Place-attached legend records and local public-history narratives.",
    "Encounter accounts": "Reported encounter-style public records, not verification of an event.",
    "Other typed context": "Typed contextual records that support source history or classification.",
  };
  const glyphs = ["++", "::", "[]", "//", "<>", "##", "..", "||", "--"];

  return NARRATIVE_MATRIX_LABELS.map((label, index) => {
    const familyRecords = records.filter((record) => displayNarrativeGroupLabel(record) === label);
    const years = familyRecords
      .map((record) => record.year)
      .filter((year): year is number => typeof year === "number" && Number.isFinite(year))
      .sort((a, b) => a - b);
    const mappedCount = familyRecords.filter((record) => mappedIds.has(record.record_id)).length;
    const involvesCulturalContext = familyRecords.some((record) => Boolean(record.involves_indigenous_knowledge));
    return {
      label,
      records: familyRecords.sort(compareRecordsByDate),
      mappedCount,
      topSourceFamily: topLabel(familyRecords, (record) => sourceFamilyFor(record.source_type).label),
      dateSpan: years.length ? `${years[0]}-${years[years.length - 1]}` : "undated only",
      description: descriptions[label] ?? descriptions["Other typed context"],
      glyph: glyphs[index % glyphs.length],
      sensitivityNote: involvesCulturalContext
        ? "Culturally specific public records need source context; publicness is not permission."
        : "Public-text grouping only; not a claim about real-world frequency.",
    };
  }).sort((a, b) => b.records.length - a.records.length || a.label.localeCompare(b.label));
}

function topLabel(records: readonly RecordItem[], labelFor: (record: RecordItem) => string) {
  if (!records.length) {
    return "No dated records";
  }
  return entriesDescending(
    records.reduce<Record<string, number>>((acc, record) => {
      const label = labelFor(record);
      acc[label] = (acc[label] ?? 0) + 1;
      return acc;
    }, {}),
    1,
  )[0]?.[0] ?? "No dated records";
}

function DashboardView({
  data,
  derived,
  onSelectRecord,
}: {
  data: FrontendData;
  derived: FrontendDerivedData;
  onSelectRecord: (record: RecordItem) => void;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [layout, setLayout] = useState<DashboardLayout>("balanced");

  useDashboardLayoutMotion(rootRef, layout);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setLayout("balanced");
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const target = entry.target as HTMLElement;
        target.style.setProperty("--dashboard-panel-width", `${Math.round(entry.contentRect.width)}px`);
      }
    });
    root.querySelectorAll<HTMLElement>(".dashboard-track-network, .dashboard-console").forEach((panel) => observer.observe(panel));
    return () => observer.disconnect();
  }, []);

  const toggleLayout = useCallback((side: "left" | "right") => {
    setLayout((current) => {
      const next: DashboardLayout = side === "left" ? "left-expanded" : "right-expanded";
      return current === next ? "balanced" : next;
    });
  }, []);

  return (
    <div ref={rootRef} className="dashboard-view" data-dashboard-layout={layout}>
      <DashboardTrackNetwork
        data={data}
        derived={derived}
        layout={layout}
        onToggle={() => toggleLayout("left")}
        onSelectRecord={onSelectRecord}
      />
      <DashboardControlConsole
        data={data}
        derived={derived}
        layout={layout}
        onToggle={() => toggleLayout("right")}
      />
    </div>
  );
}

function DashboardExpandButton({
  side,
  expanded,
  onToggle,
}: {
  side: "left" | "right";
  expanded: boolean;
  onToggle: () => void;
}) {
  const title = side === "left" ? "record network" : "corpus console";
  const glyph = expanded ? "×" : side === "left" ? ">" : "<";

  return (
    <button
      className={`dashboard-expand-control dashboard-expand-${side}`}
      type="button"
      aria-expanded={expanded}
      aria-label={expanded ? `Collapse ${title}` : `Expand ${title}`}
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
    >
      {glyph}
    </button>
  );
}

const DASHBOARD_LAYOUT_TARGETS: Record<DashboardLayout, { left: string; right: string }> = {
  balanced: { left: "54%", right: "46%" },
  "left-expanded": { left: "74%", right: "26%" },
  "right-expanded": { left: "26%", right: "74%" },
};

function useDashboardLayoutMotion(rootRef: RefObject<HTMLDivElement | null>, layout: DashboardLayout) {
  const reducedMotion = usePrefersReducedMotion();
  const timelineRef = useRef<Timeline | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) {
      return;
    }
    const leftPanel = root.querySelector<HTMLElement>('[data-dashboard-panel="left"]');
    const rightPanel = root.querySelector<HTMLElement>('[data-dashboard-panel="right"]');
    if (!leftPanel || !rightPanel) {
      return;
    }

    timelineRef.current?.cancel();
    timelineRef.current = null;

    const target = DASHBOARD_LAYOUT_TARGETS[layout];
    if (reducedMotion) {
      leftPanel.style.flexBasis = target.left;
      rightPanel.style.flexBasis = target.right;
      resetDashboardMotion(root);
      return;
    }

    prepareDashboardDrawPaths(root);

    const timeline = createTimeline({
      defaults: {
        ease: "inOutCubic",
        composition: "replace",
      },
    });

    timeline
      .add(leftPanel, { flexBasis: target.left, duration: layout === "balanced" ? 380 : 520 }, 0)
      .add(rightPanel, { flexBasis: target.right, duration: layout === "balanced" ? 380 : 520 }, 0);
    addIfTargets(timeline, root.querySelectorAll(".dashboard-draw-path, .console-polyline polyline"), { strokeDashoffset: 0, duration: 860, delay: stagger(22) }, 120);
    addIfTargets(timeline, root.querySelectorAll(".network-slot-label, .track-row small, .console-effect-grid span, .source-wheel-list span"), {
      opacity: [0, 1],
      translateY: [4, 0],
      duration: 420,
      delay: stagger(22),
    }, 180);
    addIfTargets(timeline, root.querySelectorAll(".dashboard-highlight-point"), {
      filter: [
        "drop-shadow(0 0 0 rgba(159, 227, 107, 0))",
        "drop-shadow(0 0 10px rgba(159, 227, 107, .58))",
        "drop-shadow(0 0 2px rgba(159, 227, 107, .2))",
      ],
      duration: 420,
      delay: stagger(90),
    }, 620);

    timelineRef.current = timeline;

    return () => {
      timeline.cancel();
    };
  }, [layout, reducedMotion, rootRef]);

  useEffect(() => {
    return () => {
      timelineRef.current?.cancel();
      timelineRef.current = null;
    };
  }, []);
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return reduced;
}

function prepareDashboardDrawPaths(root: HTMLElement) {
  root.querySelectorAll<SVGGeometryElement>(".dashboard-draw-path, .console-polyline polyline").forEach((path) => {
    const length = Math.max(1, path.getTotalLength());
    path.style.strokeDasharray = String(length);
    path.style.strokeDashoffset = String(length);
  });
}

function resetDashboardMotion(root: HTMLElement) {
  root.querySelectorAll<SVGGeometryElement>(".dashboard-draw-path, .console-polyline polyline").forEach((path) => {
    path.style.strokeDasharray = "";
    path.style.strokeDashoffset = "";
  });
  root.querySelectorAll<HTMLElement>(".network-slot-label, .track-row small, .console-effect-grid span, .source-wheel-list span").forEach((element) => {
    element.style.opacity = "";
    element.style.transform = "";
  });
}

function DashboardTrackNetwork({
  data,
  derived,
  layout,
  onToggle,
  onSelectRecord,
}: {
  data: FrontendData;
  derived: FrontendDerivedData;
  layout: DashboardLayout;
  onToggle: () => void;
  onSelectRecord: (record: RecordItem) => void;
}) {
  const expanded = layout === "left-expanded";
  const contracted = layout === "right-expanded";
  const [activeTrackIndex, setActiveTrackIndex] = useState<number | null>(null);
  const [hoverRelationKey, setHoverRelationKey] = useState<string | null>(null);
  const [lockedRelationKey, setLockedRelationKey] = useState<string | null>(null);
  const graph = useMemo(() => {
    const records = data.records;
    const relationMap = new Map<string, RelationGroup>();
    const sourceCounts: Record<string, number> = {};
    const periodCounts: Record<string, number> = {};
    const narrativeCounts: Record<string, number> = {};
    const placeCounts: Record<string, number> = {};
    const recordRelationKeys = new Map<number, string>();

    for (const record of records) {
      const parts = recordRelationParts(data, record);
      sourceCounts[parts.source] = (sourceCounts[parts.source] ?? 0) + 1;
      periodCounts[parts.periodId] = (periodCounts[parts.periodId] ?? 0) + 1;
      narrativeCounts[parts.narrative] = (narrativeCounts[parts.narrative] ?? 0) + 1;
      placeCounts[parts.place] = (placeCounts[parts.place] ?? 0) + 1;
      recordRelationKeys.set(record.record_id, parts.key);

      const existing = relationMap.get(parts.key);
      if (existing) {
        existing.records.push(record);
        existing.count += 1;
        existing.placeCounts[parts.place] = (existing.placeCounts[parts.place] ?? 0) + 1;
      } else {
        relationMap.set(parts.key, {
          key: parts.key,
          source: parts.source,
          periodId: parts.periodId,
          periodLabel: parts.periodLabel,
          narrative: parts.narrative,
          place: parts.place,
          count: 1,
          records: [record],
          placeCounts: { [parts.place]: 1 },
        });
      }
    }

    const relations = [...relationMap.values()]
      .map((relation) => {
        relation.records.sort(
          (a, b) =>
            (a.year ?? 9999) - (b.year ?? 9999) ||
            (a.publication || a.source_name || "").localeCompare(b.publication || b.source_name || "") ||
            (a.title || "").localeCompare(b.title || ""),
        );
        const topPlace = entriesDescending(relation.placeCounts, 1)[0]?.[0] ?? relation.place;
        return { ...relation, place: topPlace };
      })
      .sort((a, b) => b.count - a.count || a.source.localeCompare(b.source) || a.periodLabel.localeCompare(b.periodLabel));

    const strongestRelationFor = (predicate: (relation: RelationGroup) => boolean) => relations.find(predicate)?.key ?? relations[0]?.key ?? "";
    const laneX: Record<RelationLane, number> = {
      source: expanded ? 104 : 92,
      period: expanded ? 282 : 266,
      narrative: expanded ? 464 : 454,
      place: expanded ? 642 : 628,
    };
    const laneY = (index: number, total: number) => {
      const min = expanded ? 76 : 84;
      const max = expanded ? 396 : 382;
      return total <= 1 ? (min + max) / 2 : min + (index / (total - 1)) * (max - min);
    };
    const sourceEntries = entriesDescending(sourceCounts, expanded ? 7 : 5);
    const periodEntries = data.date_bands.map((band) => [band.id, periodCounts[band.id] ?? 0, band.label] as const);
    const narrativeEntries = entriesDescending(narrativeCounts, expanded ? 8 : 6);
    const orderedPlaceEntries = DASHBOARD_STATE_ORDER.map((state) => [state, placeCounts[state] ?? 0] as const)
      .filter(([, value]) => value > 0)
      .sort((a, b) => b[1] - a[1]);
    const broadPlace = placeCounts["Broad / unmapped"] ? [["Broad / unmapped", placeCounts["Broad / unmapped"]] as const] : [];
    const placeEntries = [...orderedPlaceEntries, ...broadPlace].slice(0, expanded ? 8 : 5);
    const nodes: RelationNode[] = [
      ...sourceEntries.map(([label, count], index) => ({
        id: `source:${label}`,
        lane: "source" as const,
        key: label,
        label,
        count,
        x: laneX.source,
        y: laneY(index, sourceEntries.length),
        relationKey: strongestRelationFor((relation) => relation.source === label),
        sourceClass: sourceGraphClass(label),
      })),
      ...periodEntries.map(([id, count, label], index) => ({
        id: `period:${id}`,
        lane: "period" as const,
        key: id,
        label,
        count,
        x: laneX.period,
        y: laneY(index, periodEntries.length),
        relationKey: strongestRelationFor((relation) => relation.periodId === id),
      })),
      ...narrativeEntries.map(([label, count], index) => ({
        id: `narrative:${label}`,
        lane: "narrative" as const,
        key: label,
        label,
        count,
        x: laneX.narrative,
        y: laneY(index, narrativeEntries.length),
        relationKey: strongestRelationFor((relation) => relation.narrative === label),
      })),
      ...placeEntries.map(([label, count], index) => ({
        id: `place:${label}`,
        lane: "place" as const,
        key: label,
        label,
        count,
        x: laneX.place,
        y: laneY(index, placeEntries.length),
        relationKey: strongestRelationFor((relation) => relation.place === label || Boolean(relation.placeCounts[label])),
      })),
    ];
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const edgeCounts = new Map<string, RelationEdge>();
    const bumpEdge = (from: string, to: string, kind: RelationEdge["kind"], sourceLabel?: string) => {
      if (!nodeById.has(from) || !nodeById.has(to)) {
        return;
      }
      const key = `${kind}:${from}->${to}`;
      const edge = edgeCounts.get(key);
      if (edge) {
        edge.count += 1;
      } else {
        edgeCounts.set(key, { key, from, to, kind, count: 1, sourceLabel });
      }
    };

    for (const record of records) {
      const parts = recordRelationParts(data, record);
      bumpEdge(`source:${parts.source}`, `period:${parts.periodId}`, "source-period", parts.source);
      bumpEdge(`period:${parts.periodId}`, `narrative:${parts.narrative}`, "period-narrative");
      bumpEdge(`narrative:${parts.narrative}`, `place:${parts.place}`, "narrative-place");
    }

    return {
      relations,
      nodes,
      nodeById,
      edges: [...edgeCounts.values()],
      recordRelationKeys,
    };
  }, [data, expanded]);
  const activeRelationKey = lockedRelationKey || hoverRelationKey || graph.relations[0]?.key || "";
  const activeRelation = graph.relations.find((relation) => relation.key === activeRelationKey) ?? graph.relations[0];
  const activeNodeIds = activeRelation
    ? new Set([
        `source:${activeRelation.source}`,
        `period:${activeRelation.periodId}`,
        `narrative:${activeRelation.narrative}`,
        `place:${activeRelation.place}`,
      ])
    : new Set<string>();
  const visibleTracks = activeRelation?.records.slice(0, expanded ? 30 : 14) ?? dashboardTrackSample(data, expanded ? 30 : 14);
  const relationTitle = activeRelation
    ? `${activeRelation.source} / ${activeRelation.periodLabel} / ${activeRelation.narrative}`
    : "Representative public relations";
  const setHoverRelation = (key: string | null) => {
    if (!lockedRelationKey) {
      setHoverRelationKey(key);
    }
  };

  return (
    <section
      className={`dashboard-track-network dash-hover-zone${expanded ? " is-expanded" : ""}${contracted ? " is-contracted" : ""}`}
      data-dashboard-panel="left"
      aria-label="Record network and track list"
    >
      <DashboardExpandButton side="left" expanded={expanded} onToggle={onToggle} />
      <svg className="network-svg" viewBox="0 0 760 520" role="img" aria-label="Archive record signal network">
        <path className="corner-mark top-left" d="M72 34 h-20 v20 M72 34 v-22" />
        <path className="corner-mark top-right" d="M690 34 h20 v20 M690 34 v-22" />
        <path className="corner-mark bottom-left" d="M72 486 h-20 v-20 M72 486 v22" />
        <path className="corner-mark bottom-right" d="M690 486 h20 v-20 M690 486 v22" />
        <rect className="network-wave-box network-field-box" x="42" y="58" width="676" height="396" />
        {(["source", "period", "narrative", "place"] as RelationLane[]).map((lane) => {
          const node = graph.nodes.find((item) => item.lane === lane);
          return (
            <g className={`relation-lane relation-lane-${lane}`} key={lane}>
              <line x1={node?.x ?? 0} x2={node?.x ?? 0} y1="62" y2="444" />
              <text x={(node?.x ?? 0) - 52} y="48">{lane.toUpperCase()}</text>
            </g>
          );
        })}
        {graph.edges.map((edge) => {
          const from = graph.nodeById.get(edge.from);
          const to = graph.nodeById.get(edge.to);
          const path = relationPath(from, to);
          const isActive =
            activeRelation
            && ((edge.kind === "source-period" && edge.from === `source:${activeRelation.source}` && edge.to === `period:${activeRelation.periodId}`)
              || (edge.kind === "period-narrative" && edge.from === `period:${activeRelation.periodId}` && edge.to === `narrative:${activeRelation.narrative}`)
              || (edge.kind === "narrative-place" && edge.from === `narrative:${activeRelation.narrative}` && edge.to === `place:${activeRelation.place}`));
          const isRelated = activeNodeIds.has(edge.from) || activeNodeIds.has(edge.to);
          return (
            <path
              className={`relation-edge relation-edge-${edge.kind} ${sourceGraphClass(edge.sourceLabel ?? "")}${isActive ? " is-active" : isRelated ? " is-related" : ""} dashboard-draw-path`}
              d={path}
              key={edge.key}
              style={{ "--edge-weight": String(Math.min(2.4, 0.7 + Math.sqrt(edge.count) / 18)) } as CSSProperties}
            />
          );
        })}
        {activeRelation ? (
          <g className="relation-active-path">
            {[
              [`source:${activeRelation.source}`, `period:${activeRelation.periodId}`],
              [`period:${activeRelation.periodId}`, `narrative:${activeRelation.narrative}`],
              [`narrative:${activeRelation.narrative}`, `place:${activeRelation.place}`],
            ].map(([from, to]) => {
              const path = relationPath(graph.nodeById.get(from), graph.nodeById.get(to));
              return path ? <path className="relation-edge-halo" d={path} key={`${from}-${to}`} /> : null;
            })}
          </g>
        ) : null}
        {graph.nodes.map((node) => (
          <g
            key={node.id}
            className={`relation-node relation-node-${node.lane} ${node.sourceClass ?? ""}${activeNodeIds.has(node.id) ? " is-active" : ""}`}
            onMouseEnter={() => setHoverRelation(node.relationKey)}
            onMouseLeave={() => setHoverRelation(null)}
            onFocus={() => setHoverRelation(node.relationKey)}
            onBlur={() => setHoverRelation(null)}
            onClick={() => setLockedRelationKey((current) => current === node.relationKey ? null : node.relationKey)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setLockedRelationKey((current) => current === node.relationKey ? null : node.relationKey);
              }
            }}
            role="button"
            tabIndex={0}
            aria-label={`${node.lane} node ${node.label}, ${node.count} records`}
          >
            <rect className="relation-node-hitbox" x={node.x - 68} y={node.y - 18} width="136" height="36" />
            <circle className="relation-node-anchor" cx={node.x - 62} cy={node.y} r="3.5" />
            <rect className="relation-node-box" x={node.x - 54} y={node.y - 15} width="108" height="30" />
            <text className="relation-node-label" x={node.x - 48} y={node.y - 2}>
              {truncate(node.label, expanded ? 19 : 13)}
            </text>
            <text className="relation-node-count" x={node.x - 48} y={node.y + 10}>
              {numberFormat(node.count)}
            </text>
          </g>
        ))}
        <g className="relation-style-legend">
          <text x="54" y="474">SOURCE STYLE</text>
          <line className="source-repository" x1="154" y1="471" x2="190" y2="471" />
          <text x="196" y="474">repository</text>
          <line className="source-public-domain" x1="294" y1="471" x2="330" y2="471" />
          <text x="336" y="474">public-domain</text>
          <line className="source-modern-web" x1="468" y1="471" x2="504" y2="471" />
          <text x="510" y="474">modern web</text>
          <line className="source-academic" x1="616" y1="471" x2="652" y2="471" />
          <text x="658" y="474">academic</text>
        </g>
      </svg>
      <div className="mobile-track-snapshot" aria-label="Compact track relation preview">
        <div className="mobile-track-snapshot-header">
          <b>TRACKS</b>
          <span>{truncate(relationTitle, 46)}</span>
          <small>{numberFormat(activeRelation?.count ?? visibleTracks.length)} records · ordered by year</small>
        </div>
        <div className="mobile-track-snapshot-field">
          <svg viewBox="0 0 320 250" aria-hidden="true">
            <path className="mobile-snapshot-frame" d="M12 18 h44 v-10 M12 18 v36 M308 232 h-44 v10 M308 232 v-36" />
            <circle className="mobile-snapshot-core" cx="82" cy="126" r="5" />
            {visibleTracks.slice(0, 6).map((record, index) => {
              const y = 38 + index * 34;
              const parts = recordRelationParts(data, record);
              return (
                <path
                  className={`mobile-snapshot-wire ${sourceGraphClass(parts.source)}`}
                  d={`M86 126 C128 ${80 + index * 7}, 144 ${y}, 184 ${y}`}
                  key={record.record_id}
                />
              );
            })}
          </svg>
          <div className="mobile-track-notes">
            {visibleTracks.slice(0, 6).map((record, index) => {
              const parts = recordRelationParts(data, record);
              const relation = graph.recordRelationKeys.get(record.record_id) ?? parts.key;
              return (
                <button
                  className="mobile-track-note"
                  key={record.record_id}
                  type="button"
                  style={{ "--track-source-color": sourceGraphColor(parts.source) } as CSSProperties}
                  title={`${dashboardTrackTitle(record, 84)} / ${dashboardTrackMeta(record)}`}
                  onMouseEnter={() => {
                    setActiveTrackIndex(index);
                    setHoverRelation(relation);
                  }}
                  onMouseLeave={() => {
                    setActiveTrackIndex(null);
                    setHoverRelation(null);
                  }}
                  onFocus={() => {
                    setActiveTrackIndex(index);
                    setHoverRelation(relation);
                  }}
                  onBlur={() => {
                    setActiveTrackIndex(null);
                    setHoverRelation(null);
                  }}
                  onClick={() => {
                    setLockedRelationKey(relation);
                    onSelectRecord(record);
                  }}
                >
                  <b>{String(index + 1).padStart(2, "0")}.</b>
                  <span>{dashboardTrackTitle(record, 30)}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
      <div className="track-list">
        <div className="track-list-header">
          <span>TRACKS · {truncate(relationTitle, expanded ? 82 : 30)}</span>
          {lockedRelationKey ? <button type="button" onClick={() => setLockedRelationKey(null)}>CLEAR</button> : null}
          <small>{numberFormat(activeRelation?.count ?? visibleTracks.length)} records · ordered by year / source / title</small>
        </div>
        <div className="track-list-rows">
          {visibleTracks.map((record, index) => {
            const parts = recordRelationParts(data, record);
            const relation = graph.recordRelationKeys.get(record.record_id) ?? parts.key;
            return (
              <button
                className={`track-row${activeTrackIndex === index ? " is-active" : ""}`}
                key={record.record_id}
                type="button"
                style={{ "--track-source-color": sourceGraphColor(parts.source) } as CSSProperties}
                title={`${dashboardTrackTitle(record, 84)} / ${dashboardTrackMeta(record)} / ${parts.narrative}`}
                aria-label={`Open record ${String(index + 1).padStart(2, "0")}: ${dashboardTrackTitle(record, 84)}. ${dashboardTrackMeta(record)}. ${parts.narrative}.`}
                onMouseEnter={() => {
                  setActiveTrackIndex(index);
                  setHoverRelation(relation);
                }}
                onMouseLeave={() => {
                  setActiveTrackIndex(null);
                  setHoverRelation(null);
                }}
                onFocus={() => {
                  setActiveTrackIndex(index);
                  setHoverRelation(relation);
                }}
                onBlur={() => {
                  setActiveTrackIndex(null);
                  setHoverRelation(null);
                }}
                onClick={() => {
                  setLockedRelationKey(relation);
                  onSelectRecord(record);
                }}
              >
                <b>{String(index + 1).padStart(2, "0")}.</b>
                <i>
                  <span>{dashboardTrackTitle(record, expanded ? 64 : 26)}</span>
                  <small>{dashboardTrackMeta(record)} / {parts.narrative}</small>
                </i>
              </button>
            );
          })}
        </div>
      </div>
      <div className="network-footer">
        <span>PUBLIC DATA FIELD</span>
        <span>{data.summary.record_count} RECORDS</span>
        <span>{derived.mapFlags.length} MAPPED</span>
      </div>
    </section>
  );
}

function DashboardControlConsole({
  data,
  derived,
  layout,
  onToggle,
}: {
  data: FrontendData;
  derived: FrontendDerivedData;
  layout: DashboardLayout;
  onToggle: () => void;
}) {
  const [mode, setMode] = useState<ConsoleMode>("sources");
  const expanded = layout === "right-expanded";
  const contracted = layout === "left-expanded";
  const [selectedBandId, setSelectedBandId] = useState<string>("all");
  const datedBands = useMemo(() => data.date_bands.filter((band) => band.id !== "undated"), [data.date_bands]);
  const selectedBand = datedBands.find((band) => band.id === selectedBandId) ?? null;
  const scopedRecords = useMemo(
    () => (selectedBand ? data.records.filter((record) => record.date_band === selectedBand.id) : data.records),
    [data.records, selectedBand],
  );
  const scopedMapFlags = useMemo(
    () => (selectedBand ? derived.mapFlags.filter((flag) => flag.record.date_band === selectedBand.id) : derived.mapFlags),
    [derived.mapFlags, selectedBand],
  );
  const contentRef = useRef<HTMLDivElement | null>(null);
  const aggregate = useMemo(
    () => buildDashboardFieldAggregate({
      records: scopedRecords,
      mapFlags: scopedMapFlags,
      dateBands: datedBands,
      binCount: expanded ? 20 : 12,
    }),
    [datedBands, expanded, scopedMapFlags, scopedRecords],
  );
  useDashboardFieldMotion(contentRef, mode);
  const activeTabs = [
    { id: "records" as const, label: "RECORDS" },
    { id: "locations" as const, label: "GEO FIELD" },
    { id: "sources" as const, label: "SOURCE FIELD" },
  ];
  const outputValues = [
    { id: "records" as const, value: scopedRecords.length, label: "Card-ready records" },
    { id: "locations" as const, value: scopedMapFlags.length, label: "Mapped records" },
    { id: "sources" as const, value: aggregate.sourceFamilies.filter((family) => family.count > 0).length, label: "Source families" },
  ];

  return (
    <section
      className={`dashboard-console dashboard-right-scroll dash-hover-zone${expanded ? " is-expanded" : ""}${contracted ? " is-contracted" : ""}`}
      data-dashboard-panel="right"
      aria-label="Public corpus control console"
    >
      <DashboardExpandButton side="right" expanded={expanded} onToggle={onToggle} />
      <header className="console-header">
        <div>
          <span>PUBLIC FIELD:</span>
          <b>AU HUMANOID SIGNAL</b>
        </div>
        <div className="output-switch" aria-label="Output density">
          {outputValues.map((item) => (
            <button
              className={mode === item.id ? "active" : ""}
              key={item.id}
              type="button"
              onClick={() => setMode(item.id)}
              aria-pressed={mode === item.id}
              aria-label={item.label}
              title={item.label}
            >
              {item.value}
          </button>
        ))}
      </div>
      </header>

      <div className="dashboard-right-sticky">
        <div className="console-tabs">
          {activeTabs.map((tab) => (
            <button
              className={mode === tab.id ? "active" : ""}
              key={tab.id}
              type="button"
              onClick={() => setMode(tab.id)}
              aria-pressed={mode === tab.id}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <TimeCutter bands={datedBands} selectedBandId={selectedBandId} onSelect={setSelectedBandId} />
      </div>

      <div ref={contentRef} className="dashboard-field-content" data-field={mode}>
        {mode === "records" ? (
          <RecordsFieldView aggregate={aggregate} bands={datedBands} expanded={expanded} scopeLabel={selectedBand?.label ?? "complete archive"} />
        ) : null}
        {mode === "locations" ? (
          <GeoFieldView aggregate={aggregate} expanded={expanded} scopeLabel={selectedBand?.label ?? "complete archive"} />
        ) : null}
        {mode === "sources" ? (
          <SourceFieldView aggregate={aggregate} bands={datedBands} expanded={expanded} scopeLabel={selectedBand?.label ?? "complete archive"} />
        ) : null}
      </div>
    </section>
  );
}

function TimeCutter({
  bands,
  selectedBandId,
  onSelect,
}: {
  bands: readonly DateBand[];
  selectedBandId: string;
  onSelect: (id: string) => void;
}) {
  const activeBand = bands.find((band) => band.id === selectedBandId);

  return (
    <div className="console-sequencer time-cutter">
      <span className="tiny-label">TIME CUTTER {activeBand ? `/ ${activeBand.label}` : "/ ALL PUBLIC RECORDS"}</span>
      <div className="time-cutter-grid">
        {bands.map((band, index) => (
          <button
            key={band.id}
            type="button"
            className={`${band.record_count > 0 ? "lit" : ""}${selectedBandId === band.id ? " active" : ""}`}
            onClick={() => onSelect(selectedBandId === band.id ? "all" : band.id)}
            aria-pressed={selectedBandId === band.id}
            aria-label={`${selectedBandId === band.id ? "Clear" : "Show"} ${band.label} records`}
            title={`${band.label}: ${band.record_count} archive records`}
          >
            <b className="time-cutter-number">{index + 1}</b>
            <small className="time-cutter-period">{band.label}</small>
            <em className="time-cutter-count">{numberFormat(band.record_count)} records</em>
          </button>
        ))}
      </div>
    </div>
  );
}

function RecordsFieldView({
  aggregate,
  bands,
  expanded,
  scopeLabel,
}: {
  aggregate: DashboardFieldAggregate;
  bands: readonly DateBand[];
  expanded: boolean;
  scopeLabel: string;
}) {
  if (!expanded) {
    const mappedShare = aggregate.totalRecords ? Math.round((aggregate.totalMapped / aggregate.totalRecords) * 100) : 0;
    return (
      <div className="dashboard-field-view records-field-view records-field-preview">
        <RecordSignalChart points={aggregate.timeline} compact />
        <div className="field-preview-metrics">
          <MiniControl label="RECORDS" value={aggregate.totalRecords} />
          <MiniControl label="MAPPED SHARE" value={mappedShare} />
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-field-view records-field-view">
      <div className="dashboard-field-row records-top-row">
        <RecordSignalChart points={aggregate.timeline} scopeLabel={scopeLabel} />
        <NarrativePeriodMatrix rows={aggregate.narrativePeriodRows} bands={bands} />
      </div>
      <SelectedPeriodDetail aggregate={aggregate} scopeLabel={scopeLabel} />
    </div>
  );
}

function GeoFieldView({
  aggregate,
  expanded,
  scopeLabel,
}: {
  aggregate: DashboardFieldAggregate;
  expanded: boolean;
  scopeLabel: string;
}) {
  const mappedShare = aggregate.totalRecords ? Math.round((aggregate.totalMapped / aggregate.totalRecords) * 100) : 0;
  if (!expanded) {
    return (
      <div className="dashboard-field-view geo-field-view geo-field-preview">
        <StateCoverageChart rows={aggregate.stateRows} compact />
        <div className="field-preview-metrics">
          <MiniControl label="MAPPED" value={aggregate.totalMapped} />
          <MiniControl label="MAP SHARE" value={mappedShare} />
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-field-view geo-field-view">
      <div className="dashboard-field-row geo-top-row">
        <StateCoverageChart rows={aggregate.stateRows} scopeLabel={scopeLabel} />
        <LocationPrecisionChart rows={aggregate.precisionRows} total={aggregate.totalRecords} />
      </div>
      <PlaceRoleMatrix rows={aggregate.placeRoleRows} bands={aggregate.dateBands} />
      <p className="dashboard-field-disclaimer">Mapped points represent documented narrative geography, not verified supernatural distribution.</p>
    </div>
  );
}

function SourceFieldView({
  aggregate,
  bands,
  expanded,
  scopeLabel,
}: {
  aggregate: DashboardFieldAggregate;
  bands: readonly DateBand[];
  expanded: boolean;
  scopeLabel: string;
}) {
  if (!expanded) {
    return (
      <div className="dashboard-field-view source-field-view source-field-preview">
        <SourcePeriodRibbon families={aggregate.sourceFamilies} bands={bands} compact />
        <SourceDonut families={aggregate.sourceFamilies} compact />
      </div>
    );
  }

  return (
    <div className="dashboard-field-view source-field-view">
      <SourcePeriodRibbon families={aggregate.sourceFamilies} bands={bands} scopeLabel={scopeLabel} />
      <div className="dashboard-field-row source-bottom-row">
        <SourceDonut families={aggregate.sourceFamilies} />
        <RankedSourceBars families={aggregate.sourceFamilies} bands={bands} />
      </div>
    </div>
  );
}

function RecordSignalChart({
  points,
  scopeLabel = "complete archive",
  compact = false,
}: {
  points: TimelineLayerPoint[];
  scopeLabel?: string;
  compact?: boolean;
}) {
  const max = Math.max(...points.map((point) => point.value), 1);
  const maxDiversity = Math.max(...points.map((point) => point.diversity), 1);
  const width = 640;
  const height = compact ? 132 : 246;
  const left = 44;
  const right = 18;
  const top = compact ? 24 : 34;
  const bottom = compact ? 28 : 42;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const xFor = (index: number) => left + (index / Math.max(1, points.length - 1)) * plotWidth;
  const yFor = (value: number) => top + plotHeight - (value / max) * plotHeight;
  const barWidth = Math.max(5, Math.min(20, plotWidth / Math.max(1, points.length) * 0.58));
  const totalLine = points.map((point, index) => `${xFor(index).toFixed(1)},${yFor(point.value).toFixed(1)}`).join(" ");
  const mappedLine = points.map((point, index) => `${xFor(index).toFixed(1)},${yFor(point.mapped).toFixed(1)}`).join(" ");
  const peakPoints = [...points].map((point, index) => ({ point, index })).sort((a, b) => b.point.value - a.point.value).slice(0, compact ? 1 : 3);
  const peakIndexes = new Set(peakPoints.map((peak) => peak.index));
  const labelStep = Math.max(1, Math.ceil(points.length / (compact ? 3 : 5)));

  return (
    <section className="dashboard-chart-module record-signal-module">
      {!compact ? (
        <header className="module-heading">
          <span>RECORD TIME SIGNAL</span>
          <small>Archive records by period, not the real-world frequency of a phenomenon.</small>
        </header>
      ) : null}
      <svg className="record-signal-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Record time signal for ${scopeLabel}`}>
        {[0, 0.5, 1].map((tick) => (
          <g key={tick}>
            <line className="timeline-grid-line" x1={left} x2={width - right} y1={yFor(max * tick)} y2={yFor(max * tick)} />
            <text className="dashboard-svg-micro" x="8" y={yFor(max * tick) + 4}>
              {tick === 0 ? "0" : tick === 1 ? numberFormat(max) : numberFormat(Math.round(max / 2))}
            </text>
          </g>
        ))}
        {points.map((point, index) => (
          <rect
            key={`bar-${point.key}`}
            className="record-signal-bar"
            data-animate="record-bar"
            x={xFor(index) - barWidth / 2}
            y={yFor(point.value)}
            width={barWidth}
            height={top + plotHeight - yFor(point.value)}
          />
        ))}
        <polyline className="timeline-total-line dashboard-draw-path" points={totalLine} />
        <polyline className="timeline-mapped-line dashboard-draw-path" points={mappedLine} />
        {points.map((point, index) => (
          <circle
            key={`diversity-${point.key}`}
            className="timeline-diversity-dot"
            cx={xFor(index)}
            cy={height - bottom + 8 - (point.diversity / maxDiversity) * 12}
            r={compact ? 1.8 : 2.5}
          />
        ))}
        {points.map((point, index) =>
          peakIndexes.has(index) ? (
            <g key={`peak-${point.key}`}>
              <circle className="dashboard-highlight-point" cx={xFor(index)} cy={yFor(point.value)} r={compact ? 4 : 5} />
              {!compact ? (
                <text className="timeline-peak-label" x={Math.min(width - 56, xFor(index) + 8)} y={Math.max(18, yFor(point.value) - 6)}>
                  {numberFormat(point.value)}
                </text>
              ) : null}
            </g>
          ) : null,
        )}
        {!compact ? (
          <g className="timeline-legend">
            <rect className="record-signal-bar" x={width - 184} y="14" width="16" height="7" />
            <text x={width - 164} y="20">all records</text>
            <line className="timeline-mapped-line" x1={width - 102} y1="17" x2={width - 82} y2="17" />
            <text x={width - 76} y="20">mapped</text>
            <circle className="timeline-diversity-dot" cx={width - 184} cy="32" r="2.5" />
            <text x={width - 176} y="35">narrative families</text>
          </g>
        ) : null}
        {points.map((point, index) => index % labelStep === 0 || index === points.length - 1 ? (
          <text key={`label-${point.key}`} className="console-axis-label" x={xFor(index)} y={height - 8}>
            {compactChartLabel(point.label, "records")}
          </text>
        ) : null)}
      </svg>
    </section>
  );
}

function NarrativePeriodMatrix({ rows, bands }: { rows: NarrativePeriodRow[]; bands: readonly DateBand[] }) {
  const max = Math.max(...rows.flatMap((row) => row.values.map((cell) => cell.value)), 1);

  return (
    <section className="dashboard-chart-module narrative-matrix-module">
      <header className="module-heading">
        <span>NARRATIVE x PERIOD MATRIX</span>
        <small>Bubble size encodes filtered public-record count.</small>
      </header>
      <div className="narrative-matrix-grid" style={{ "--matrix-cols": bands.length } as CSSProperties}>
        <span className="matrix-corner" />
        {bands.map((band, index) => (
          <b key={band.id} className="matrix-column-label">{index + 1}</b>
        ))}
        {rows.map((row) => (
          <div className="matrix-row-fragment" key={row.label}>
            <span className="matrix-row-label">{row.label}</span>
            {row.values.map((cell) => {
              const intensity = cell.value / max;
              return (
                <i
                  key={`${row.label}-${cell.bandId}`}
                  className="matrix-bubble"
                  data-animate="matrix-cell"
                  style={{
                    "--bubble-size": `${Math.max(4, 7 + intensity * 24)}px`,
                    "--bubble-alpha": String(0.18 + intensity * 0.76),
                  } as CSSProperties}
                  title={`${row.label}, ${cell.bandLabel}: ${numberFormat(cell.value)}`}
                />
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
}

function SelectedPeriodDetail({ aggregate, scopeLabel }: { aggregate: DashboardFieldAggregate; scopeLabel: string }) {
  const mappedShare = aggregate.totalRecords ? Math.round((aggregate.totalMapped / aggregate.totalRecords) * 100) : 0;
  const maxFamily = Math.max(...aggregate.topNarratives.map((row) => row.value), 1);
  const sourceDiversity = aggregate.sourceFamilies.filter((family) => family.count > 0).length;

  return (
    <section className="dashboard-chart-module period-detail-module">
      <header className="module-heading">
        <span>SELECTED PERIOD DETAIL</span>
        <small>{scopeLabel}</small>
      </header>
      <div className="period-detail-grid">
        <MiniControl label="RECORDS" value={aggregate.totalRecords} />
        <MiniControl label="MAPPED %" value={mappedShare} />
        <MiniControl label="SOURCE TYPES" value={sourceDiversity} />
        <div className="detail-bars" aria-label="Top narrative families">
          {aggregate.topNarratives.slice(0, 5).map((row) => (
            <span key={row.label}>
              <b>{row.label}</b>
              <i style={{ "--detail-meter": `${Math.max(6, (row.value / maxFamily) * 100)}%` } as CSSProperties} />
              <em>{numberFormat(row.value)}</em>
            </span>
          ))}
        </div>
        <div className="representative-records" aria-label="Representative records">
          {aggregate.representativeRecords.map((record) => (
            <span key={record.record_id}>
              <b>{record.year ?? "----"}</b>
              <i>{dashboardTrackTitle(record, 46)}</i>
              <em>{truncate(record.state_territory || record.map_place_name || record.location_summary, 18)}</em>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function StateCoverageChart({
  rows,
  scopeLabel = "complete archive",
  compact = false,
}: {
  rows: StateCoverageRow[];
  scopeLabel?: string;
  compact?: boolean;
}) {
  const max = Math.max(...rows.map((row) => Math.max(row.total, row.mapped)), 1);

  return (
    <section className="dashboard-chart-module state-coverage-module">
      {!compact ? (
        <header className="module-heading">
          <span>STATE / TERRITORY COVERAGE</span>
          <small>{scopeLabel}</small>
        </header>
      ) : null}
      <div className="state-lollipop-chart">
        {rows.map((row) => (
          <div className="state-lollipop-row" data-animate="geo-lollipop" key={row.state} style={{ "--total": `${Math.max(3, (row.total / max) * 100)}%`, "--mapped": `${Math.max(3, (row.mapped / max) * 100)}%` } as CSSProperties}>
            <b>{row.state}</b>
            <i className="state-total-bar" />
            <i className="state-mapped-bar" />
            <em>{numberFormat(row.mapped)}</em>
          </div>
        ))}
      </div>
    </section>
  );
}

function LocationPrecisionChart({ rows, total }: { rows: PrecisionRow[]; total: number }) {
  const max = Math.max(...rows.map((row) => row.value), 1);

  return (
    <section className="dashboard-chart-module precision-module">
      <header className="module-heading">
        <span>LOCATION PRECISION PROFILE</span>
        <small>Human-readable public mapping quality.</small>
      </header>
      <div className="precision-ladder">
        {rows.map((row) => {
          const dots = Math.max(1, Math.round((row.value / max) * 14));
          return (
            <div className="precision-row" key={row.label}>
              <span>{row.label}</span>
              <i>
                {Array.from({ length: 14 }, (_, index) => (
                  <b key={`${row.label}-${index}`} className={index < dots ? "precision-dot lit" : "precision-dot"} data-animate="precision-dot" />
                ))}
              </i>
              <em>{numberFormat(row.value)} · {formatPercent(row.value, total)}</em>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function PlaceRoleMatrix({ rows, bands }: { rows: PlaceRoleRow[]; bands: readonly DateBand[] }) {
  const max = Math.max(...rows.flatMap((row) => row.values.map((cell) => cell.value)), 1);

  return (
    <section className="dashboard-chart-module place-role-module">
      <header className="module-heading">
        <span>MAPPED COVERAGE BY PLACE ROLE</span>
        <small>Period heat strip for public narrative geography.</small>
      </header>
      <div className="place-role-grid" style={{ "--matrix-cols": bands.length } as CSSProperties}>
        <span />
        {bands.map((band, index) => <b key={band.id}>{index + 1}</b>)}
        {rows.map((row) => (
          <div className="place-role-row" key={row.label}>
            <span>{row.label}</span>
            {row.values.map((cell) => (
              <i
                key={`${row.label}-${cell.bandId}`}
                style={{ "--heat": String(cell.value / max) } as CSSProperties}
                title={`${row.label}, ${cell.bandLabel}: ${numberFormat(cell.value)}`}
              />
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function SourcePeriodRibbon({
  families,
  bands,
  scopeLabel = "complete archive",
  compact = false,
}: {
  families: SourceFamilyAggregate[];
  bands: readonly DateBand[];
  scopeLabel?: string;
  compact?: boolean;
}) {
  const width = 720;
  const height = compact ? 132 : 220;
  const left = compact ? 22 : 38;
  const right = compact ? 16 : 22;
  const top = compact ? 20 : 40;
  const bottom = compact ? 24 : 34;
  const plotHeight = height - top - bottom;
  const colWidth = (width - left - right) / Math.max(1, bands.length);

  return (
    <section className="dashboard-chart-module source-ribbon-module">
      {!compact ? (
        <header className="module-heading">
          <span>SOURCE COMPOSITION THROUGH TIME</span>
          <small>Normalized stacked bands by time-cutter period for {scopeLabel}.</small>
        </header>
      ) : null}
      <svg className="source-period-ribbon" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Source composition through time">
        {bands.map((band, bandIndex) => {
          const total = families.reduce((sum, family) => sum + (family.byBand[band.id] ?? 0), 0) || 1;
          let yCursor = top + plotHeight;
          return (
            <g key={band.id}>
              {families.map((family) => {
                const value = family.byBand[band.id] ?? 0;
                const segmentHeight = (value / total) * plotHeight;
                yCursor -= segmentHeight;
                return (
                  <rect
                    key={`${family.id}-${band.id}`}
                    className="source-ribbon-segment"
                    data-animate="source-ribbon"
                    x={left + bandIndex * colWidth + 4}
                    y={yCursor}
                    width={Math.max(4, colWidth - 8)}
                    height={Math.max(value > 0 ? 1.5 : 0, segmentHeight)}
                    style={{ "--source-color": family.color } as CSSProperties}
                  />
                );
              })}
              <text className="console-axis-label" x={left + bandIndex * colWidth + colWidth / 2} y={height - 8}>{bandIndex + 1}</text>
            </g>
          );
        })}
        {!compact ? (
          <>
            <text className="dashboard-svg-micro" x="8" y={top + 4}>100%</text>
            <text className="dashboard-svg-micro" x="12" y={top + plotHeight}>0</text>
          </>
        ) : null}
      </svg>
    </section>
  );
}

function SourceDonut({ families, compact = false }: { families: SourceFamilyAggregate[]; compact?: boolean }) {
  const total = families.reduce((sum, family) => sum + family.count, 0) || 1;
  const visibleFamilies = families.filter((family) => family.count > 0);
  const gradient = sourceFamilyConicGradient(visibleFamilies);

  return (
    <section className={`dashboard-chart-module source-donut-module${compact ? " compact" : ""}`} data-animate="source-donut">
      {!compact ? (
        <header className="module-heading">
          <span>LARGE SOURCE DONUT</span>
          <small>Public source-family composition.</small>
        </header>
      ) : null}
      <div className="source-donut-layout">
        <div className="source-donut" style={{ "--source-wheel": gradient } as CSSProperties}>
          <i />
        </div>
        {!compact ? (
          <div className="source-donut-legend">
            {visibleFamilies.map((family) => (
              <span key={family.id}>
                <b style={{ "--source-color": family.color } as CSSProperties} />
                <i>{family.label}</i>
                <em>{numberFormat(family.count)} · {formatPercent(family.count, total)}</em>
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function RankedSourceBars({ families, bands }: { families: SourceFamilyAggregate[]; bands: readonly DateBand[] }) {
  const rows = families.filter((family) => family.count > 0);
  const total = rows.reduce((sum, family) => sum + family.count, 0) || 1;
  const max = Math.max(...rows.map((family) => family.count), 1);

  return (
    <section className="dashboard-chart-module source-ranked-module">
      <header className="module-heading">
        <span>RANKED SOURCE FAMILIES</span>
        <small>Count, share, and six-period mini-profile.</small>
      </header>
      <div className="ranked-source-bars">
        {rows.map((family) => {
          const profileMax = Math.max(...bands.map((band) => family.byBand[band.id] ?? 0), 1);
          return (
            <div className="source-rank-row" data-animate="source-bar" key={family.id}>
              <span>{family.label}</span>
              <b>{numberFormat(family.count)} · {formatPercent(family.count, total)}</b>
              <i style={{ "--source-meter": `${Math.max(4, (family.count / max) * 100)}%`, "--source-color": family.color } as CSSProperties} />
              <em>
                {bands.map((band) => (
                  <small
                    key={`${family.id}-${band.id}`}
                    style={{ "--spark-height": `${Math.max(12, ((family.byBand[band.id] ?? 0) / profileMax) * 100)}%`, "--source-color": family.color } as CSSProperties}
                    title={`${band.label}: ${numberFormat(family.byBand[band.id] ?? 0)}`}
                  />
                ))}
              </em>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function useDashboardFieldMotion(rootRef: RefObject<HTMLDivElement | null>, mode: ConsoleMode) {
  const reducedMotion = usePrefersReducedMotion();
  const timelineRef = useRef<Timeline | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) {
      return;
    }

    timelineRef.current?.cancel();
    timelineRef.current = null;

    if (reducedMotion) {
      root.querySelectorAll<HTMLElement | SVGElement>("[data-animate], .dashboard-field-view").forEach((element) => {
        element.style.opacity = "";
        element.style.transform = "";
        element.style.clipPath = "";
      });
      resetDashboardMotion(root);
      return;
    }

    prepareDashboardDrawPaths(root);
    const timeline = createTimeline({
      defaults: {
        ease: "outCubic",
        composition: "replace",
      },
    });

    addIfTargets(timeline, root.querySelectorAll(".dashboard-field-view"), {
      opacity: [0, 1],
      translateY: [8, 0],
      clipPath: ["inset(0 0 18% 0)", "inset(0 0 0% 0)"],
      duration: 220,
    }, 0);

    if (mode === "records") {
      addIfTargets(timeline, root.querySelectorAll(".record-signal-bar"), { opacity: [0, 1], scaleY: [0.18, 1], duration: 320, delay: stagger(14) }, 120);
      addIfTargets(timeline, root.querySelectorAll(".record-signal-chart .dashboard-draw-path"), { strokeDashoffset: 0, duration: 480, delay: stagger(34) }, 180);
      addIfTargets(timeline, root.querySelectorAll(".matrix-bubble"), { opacity: [0, 1], scale: [0.2, 1], duration: 260, delay: stagger(12) }, 280);
    } else if (mode === "locations") {
      addIfTargets(timeline, root.querySelectorAll(".state-lollipop-row"), { opacity: [0, 1], translateY: [8, 0], duration: 260, delay: stagger(18) }, 120);
      addIfTargets(timeline, root.querySelectorAll(".precision-dot.lit"), { opacity: [0, 1], scale: [0.25, 1], duration: 220, delay: stagger(12) }, 260);
      addIfTargets(timeline, root.querySelectorAll(".place-role-row i"), { opacity: [0, 1], scaleX: [0.25, 1], duration: 240, delay: stagger(10) }, 340);
    } else {
      addIfTargets(timeline, root.querySelectorAll(".source-ribbon-segment"), { opacity: [0, 1], scaleY: [0.15, 1], duration: 360, delay: stagger(12) }, 120);
      addIfTargets(timeline, root.querySelectorAll(".source-donut-module"), { opacity: [0, 1], scale: [0.94, 1], duration: 280 }, 310);
      addIfTargets(timeline, root.querySelectorAll(".source-rank-row"), { opacity: [0, 1], translateX: [10, 0], duration: 260, delay: stagger(18) }, 360);
    }

    timelineRef.current = timeline;

    return () => {
      timeline.cancel();
    };
  }, [mode, reducedMotion, rootRef]);

  useEffect(() => {
    return () => {
      timelineRef.current?.cancel();
      timelineRef.current = null;
    };
  }, []);
}

function addIfTargets(timeline: Timeline, targets: NodeListOf<Element>, params: Record<string, unknown>, position: number) {
  if (targets.length > 0) {
    timeline.add(targets, params, position);
  }
}

function buildDashboardFieldAggregate({
  records,
  mapFlags,
  dateBands,
  binCount,
}: {
  records: readonly RecordItem[];
  mapFlags: readonly MapFlagRenderItem[];
  dateBands: readonly DateBand[];
  binCount: number;
}): DashboardFieldAggregate {
  const narrativeCounts: Record<string, number> = {};
  const narrativePeriodCounts = new Map<string, number>();
  const stateTotals: Record<string, number> = {};
  const precisionCounts: Record<string, number> = Object.fromEntries(PRECISION_LABELS.map((label) => [label, 0]));
  const placeRoleCounts = new Map<string, number>();
  const sourceFamilyMap = new Map<string, SourceFamilyAggregate>(
    SOURCE_FAMILIES.map((family) => [
      family.id,
      {
        id: family.id,
        label: family.label,
        color: family.color,
        count: 0,
        byBand: Object.fromEntries(dateBands.map((band) => [band.id, 0])),
      },
    ]),
  );

  for (const record of records) {
    const narrative = displayNarrativeGroupLabel(record);
    narrativeCounts[narrative] = (narrativeCounts[narrative] ?? 0) + 1;
    if (dateBands.some((band) => band.id === record.date_band)) {
      narrativePeriodCounts.set(`${narrative}::${record.date_band}`, (narrativePeriodCounts.get(`${narrative}::${record.date_band}`) ?? 0) + 1);
    }

    const state = normalizeDashboardState(record.state_territory);
    if (state) {
      stateTotals[state] = (stateTotals[state] ?? 0) + 1;
    }

    const precision = locationPrecisionLabel(record);
    precisionCounts[precision] = (precisionCounts[precision] ?? 0) + 1;

    const role = placeRoleLabel(record.map_location_role);
    if (dateBands.some((band) => band.id === record.date_band)) {
      placeRoleCounts.set(`${role}::${record.date_band}`, (placeRoleCounts.get(`${role}::${record.date_band}`) ?? 0) + 1);
    }

    const family = sourceFamilyFor(record.source_type);
    const sourceAggregate = sourceFamilyMap.get(family.id);
    if (sourceAggregate) {
      sourceAggregate.count += 1;
      if (record.date_band in sourceAggregate.byBand) {
        sourceAggregate.byBand[record.date_band] += 1;
      }
    }
  }

  const mappedCounts = mapFlags.reduce<Record<string, number>>((acc, flag) => {
    const state = normalizeDashboardState(flag.state_territory);
    if (state) {
      acc[state] = (acc[state] ?? 0) + 1;
    }
    return acc;
  }, {});

  const narrativePeriodRows = NARRATIVE_MATRIX_LABELS.map((label) => ({
    label,
    values: dateBands.map((band) => ({
      bandId: band.id,
      bandLabel: band.label,
      value: narrativePeriodCounts.get(`${label}::${band.id}`) ?? 0,
    })),
  }));

  const placeRoleRows = PLACE_ROLE_LABELS.map((label) => ({
    label,
    values: dateBands.map((band) => ({
      bandId: band.id,
      bandLabel: band.label,
      value: placeRoleCounts.get(`${label}::${band.id}`) ?? 0,
    })),
  }));

  return {
    dateBands,
    totalRecords: records.length,
    totalMapped: mapFlags.length,
    timeline: buildTimelineLayerPoints(records, mapFlags, binCount),
    narrativePeriodRows,
    topNarratives: entriesDescending(narrativeCounts, 6).map(([label, value]) => ({ label, value })),
    representativeRecords: [...records].sort(compareRecordsByDate).slice(0, 4),
    stateRows: DASHBOARD_STATE_ORDER.map((state) => ({
      state,
      total: stateTotals[state] ?? 0,
      mapped: mappedCounts[state] ?? 0,
    })),
    precisionRows: PRECISION_LABELS.map((label) => ({ label, value: precisionCounts[label] ?? 0 })),
    placeRoleRows,
    sourceFamilies: [...sourceFamilyMap.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)),
  };
}

function displayNarrativeGroupLabel(record: RecordItem) {
  const label = narrativeGroupLabel(record);
  if (label === "Ghost / apparition") {
    return "Ghost / apparition records";
  }
  if (label === "Retellings") {
    return "Retellings and adaptations";
  }
  if (label === "Rumours" || label === "Belief records") {
    return "Other typed context";
  }
  if (NARRATIVE_MATRIX_LABELS.includes(label as (typeof NARRATIVE_MATRIX_LABELS)[number])) {
    return label;
  }
  return "Other typed context";
}

function normalizeDashboardState(value: string | null | undefined) {
  if (!value) {
    return null;
  }
  const normalized = value.toUpperCase();
  return DASHBOARD_STATE_ORDER.includes(normalized as (typeof DASHBOARD_STATE_ORDER)[number]) ? normalized : null;
}

function locationPrecisionLabel(record: RecordItem) {
  const raw = (record.map_location_type || record.location_precision_status || "").toLowerCase();
  if (raw === "exact_site") {
    return "Exact site";
  }
  if (raw === "road_segment") {
    return "Road segment";
  }
  if (raw === "named_feature") {
    return "Named feature";
  }
  if (raw === "locality") {
    return "Locality";
  }
  if (raw === "town" || raw === "suburb") {
    return "Town / suburb";
  }
  if (!record.has_strict_map_point || raw === "unmapped" || raw === "country") {
    return "Unmapped";
  }
  return "Broad region";
}

function placeRoleLabel(role: string | null | undefined) {
  if (role === "apparition_location") {
    return "Apparition location";
  }
  if (role === "legend_associated_place") {
    return "Legend-associated place";
  }
  if (role === "narrative_setting") {
    return "Narrative setting";
  }
  if (role === "mentioned_place" || role === "source_visible_place" || role === "source_visible_place_hint") {
    return "Rumour circulation place";
  }
  return "Event location";
}

function sourceFamilyFor(sourceType: string | null | undefined) {
  const source = (sourceType ?? "").toLowerCase();
  if (/community/.test(source)) {
    return SOURCE_FAMILIES[5];
  }
  if (/repository/.test(source)) {
    return SOURCE_FAMILIES[0];
  }
  if (/modern_web|seeded_public_web/.test(source)) {
    return SOURCE_FAMILIES[1];
  }
  if (/public_domain|gutenberg|wikisource|sacred_texts/.test(source)) {
    return SOURCE_FAMILIES[2];
  }
  if (/institutional|municipal/.test(source)) {
    return SOURCE_FAMILIES[3];
  }
  if (/academic|catalogue|metadata|andc|archive/.test(source)) {
    return SOURCE_FAMILIES[4];
  }
  return SOURCE_FAMILIES[6];
}

function sourceFamilyConicGradient(families: SourceFamilyAggregate[]) {
  const total = families.reduce((sum, family) => sum + family.count, 0) || 1;
  let cursor = 0;
  return families
    .map((family) => {
      const start = cursor;
      cursor += (family.count / total) * 100;
      return `${family.color} ${start}% ${cursor}%`;
    })
    .join(", ");
}

function formatPercent(value: number, total: number) {
  if (!total) {
    return "0%";
  }
  return `${Math.round((value / total) * 100)}%`;
}

function MiniControl({ label, value }: { label: string; value: number }) {
  return (
    <div className="mini-control">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function ConsoleAggregateMap({
  mode,
  records,
  mapFlags,
  dateBands,
}: {
  mode: ConsoleMode;
  records: readonly RecordItem[];
  mapFlags: readonly MapFlagRenderItem[];
  dateBands: readonly DateBand[];
}) {
  const groups = useMemo(() => {
    if (mode === "locations") {
      return DASHBOARD_STATE_ORDER.map((state) => ({ key: state, label: state }));
    }
    const values =
      mode === "records"
        ? countRecordValues(records, (record) => narrativeGroupLabel(record))
        : countRecordValues(records, (record) => publicSourceLabel(record.source_type));
    return entriesDescending(values, mode === "records" ? 5 : 6).map(([key]) => ({
      key,
      label: publicDashboardValueLabel(key, mode),
    }));
  }, [mode, records]);

  const cells = useMemo(() => {
    const counts = new Map<string, number>();
    if (mode === "locations") {
      for (const flag of mapFlags) {
        const band = flag.record.date_band;
        const key = `${flag.state_territory}::${band}`;
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
    } else {
      for (const record of records) {
        const group = mode === "records" ? narrativeGroupLabel(record) : publicSourceLabel(record.source_type);
        const key = `${group}::${record.date_band}`;
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
    }
    return counts;
  }, [mapFlags, mode, records]);

  const max = Math.max(...Array.from(cells.values()), 1);
  const bandWidth = 144 / Math.max(1, dateBands.length);
  const rowHeight = 32 / Math.max(1, groups.length);

  return (
    <svg className={`console-field-map console-field-map-${mode}`} viewBox="0 0 200 48" role="img" aria-label={`${consoleModeLabel(mode)} aggregate matrix`}>
      <text className="console-field-title" x="8" y="8" fontSize="5">
        {mode === "records" ? "narrative group x period" : mode === "locations" ? "mapped state x period" : "source family x period"}
      </text>
      {dateBands.map((band, index) => (
        <text key={band.id} className="console-field-band" x={52 + index * bandWidth + bandWidth / 2} y="46" fontSize="3.6">
          {String(index + 1)}
        </text>
      ))}
      {groups.map((group, rowIndex) => (
        <g key={group.key}>
          <text className="console-field-label" x="8" y={16 + rowIndex * rowHeight + rowHeight / 2} fontSize="3.8">
            {truncate(group.label, 13)}
          </text>
          {dateBands.map((band, bandIndex) => {
            const value = cells.get(`${group.key}::${band.id}`) ?? 0;
            const intensity = value / max;
            const size = 2.4 + intensity * Math.min(8, rowHeight - 1);
            return (
              <rect
                key={`${group.key}-${band.id}`}
                className={value === max ? "console-field-cell dashboard-highlight-point" : "console-field-cell"}
                x={52 + bandIndex * bandWidth + bandWidth / 2 - size / 2}
                y={14 + rowIndex * rowHeight + rowHeight / 2 - size / 2}
                width={size}
                height={size}
                style={{ "--cell-alpha": String(0.16 + intensity * 0.72) } as CSSProperties}
              />
            );
          })}
        </g>
      ))}
    </svg>
  );
}

function RadialMeter({ label, values }: { label: string; values: Record<string, number> }) {
  const total = Object.values(values).reduce((sum, value) => sum + value, 0) || 1;
  const first = Object.values(values)[0] ?? 0;
  const angle = Math.round((first / total) * 300);

  return (
    <div className="radial-meter">
      <svg viewBox="0 0 72 72" role="img" aria-label={`${label} radial meter`}>
        <circle cx="36" cy="36" r="28" />
        <path d={`M36 36 L36 8 A28 28 0 ${angle > 180 ? 1 : 0} 1 ${36 + 28 * Math.sin((angle * Math.PI) / 180)} ${36 - 28 * Math.cos((angle * Math.PI) / 180)} Z`} />
        <circle cx="36" cy="36" r="10" />
      </svg>
      <span>{label}</span>
    </div>
  );
}

function SourceWheel({ values }: { values: Record<string, number> }) {
  const entries = entriesDescending(values, 6);
  const max = Math.max(...entries.map(([, value]) => value), 1);
  const total = Object.values(values).reduce((sum, value) => sum + value, 0) || 1;

  return (
    <div className="source-wheel-module">
      <span className="tiny-label">SOURCE COMPOSITION</span>
      <div className="source-wheel" style={{ "--source-wheel": conicGradient(values) } as CSSProperties}>
        <i />
      </div>
      <div className="source-wheel-list">
        {entries.map(([label, value]) => (
          <span key={label}>
            <b style={{ "--source-dot": `${Math.max(22, (value / max) * 100)}%` } as CSSProperties} />
            <i>{publicSourceLabel(label)}</i>
            <em>{numberFormat(value)} / {Math.round((value / total) * 100)}%</em>
          </span>
        ))}
      </div>
    </div>
  );
}

function ConsolePolyline({
  mode,
  points,
  timelineLayers,
  scopeLabel,
}: {
  mode: ConsoleMode;
  points: ConsoleChartPoint[];
  timelineLayers: TimelineLayerPoint[];
  scopeLabel: string;
}) {
  const max = Math.max(...points.map((point) => point.value), 1);
  const xFor = (index: number) => (points.length <= 1 ? 110 : 12 + (index / (points.length - 1)) * 196);
  const yFor = (value: number) => 66 - (value / max) * 44;
  const barWidth = Math.max(3.5, Math.min(11, 112 / Math.max(1, points.length)));
  const linePoints = points.map((point, index) => `${xFor(index).toFixed(1)},${yFor(point.value).toFixed(1)}`).join(" ");
  const mappedPoints = timelineLayers.map((point, index) => `${xFor(index).toFixed(1)},${yFor(point.mapped).toFixed(1)}`).join(" ");
  const maxDiversity = Math.max(...timelineLayers.map((point) => point.diversity), 1);
  const labelStep = mode === "records" ? Math.max(1, Math.ceil(points.length / 5)) : Math.max(1, Math.ceil(points.length / (mode === "sources" ? 5 : 8)));
  const isTimeSeries = mode === "records";
  const peakIndexes = new Set(
    isTimeSeries
      ? [...points]
          .map((point, index) => ({ index, value: point.value }))
          .sort((a, b) => b.value - a.value)
          .slice(0, 2)
          .map((point) => point.index)
      : [],
  );

  return (
    <svg className={`console-polyline console-polyline-${mode}`} viewBox="0 0 220 92" role="img" aria-label={`${consoleModeLabel(mode)} values for ${scopeLabel}`}>
      <text className="console-chart-label" x="10" y="11">
        {consoleModeLabel(mode)} / {scopeLabel}
      </text>
      {[0, 0.5, 1].map((tick) => (
        <g key={tick}>
          <line className="timeline-grid-line" x1="12" x2="208" y1={yFor(max * tick)} y2={yFor(max * tick)} />
          <text className="console-axis-value" x="4" y={yFor(max * tick) + 1.4}>
            {tick === 0 ? "0" : tick === 1 ? numberFormat(max) : numberFormat(Math.round(max / 2))}
          </text>
        </g>
      ))}
      {points.map((point, index) => (
        <rect
          key={`bar-${point.key}`}
          className="console-density-bar"
          x={xFor(index) - barWidth / 2}
          y={yFor(point.value)}
          width={barWidth}
          height={68 - yFor(point.value)}
        />
      ))}
      {isTimeSeries ? (
        <>
          <polyline className="timeline-total-line" points={linePoints} />
          <polyline className="timeline-mapped-line" points={mappedPoints} />
          {timelineLayers.map((point, index) => (
            <rect
              key={`${point.key}-diversity`}
              className="timeline-diversity-ribbon"
              x={xFor(index) - barWidth / 2}
              y={72 - (point.diversity / maxDiversity) * 7}
              width={barWidth}
              height={(point.diversity / maxDiversity) * 7}
            />
          ))}
          <g className="timeline-legend">
            <line className="timeline-total-line" x1="124" y1="10" x2="142" y2="10" />
            <text x="146" y="12">records</text>
            <line className="timeline-mapped-line" x1="172" y1="10" x2="190" y2="10" />
            <text x="194" y="12">mapped</text>
            <rect className="timeline-diversity-ribbon" x="124" y="15" width="18" height="3" />
            <text x="146" y="18">typed diversity</text>
          </g>
        </>
      ) : null}
      {points.map((point, index) => (
        <circle
          key={`${point.key}-point`}
          className={point.value === max || index === points.length - 1 ? "dashboard-highlight-point" : undefined}
          cx={xFor(index)}
          cy={yFor(point.value)}
          r={Math.max(1.6, Math.min(3.4, 1.3 + point.value / max * 2.2))}
        />
      ))}
      {isTimeSeries
        ? points.map((point, index) =>
            peakIndexes.has(index) ? (
              <text key={`${point.key}-peak`} className="timeline-peak-label" x={Math.min(194, xFor(index) + 4)} y={Math.max(18, yFor(point.value) - 4)}>
                {numberFormat(point.value)}
              </text>
            ) : null,
          )
        : null}
      {mode === "sources"
        ? null
        : points.map((point, index) => index % labelStep === 0 || index === points.length - 1 ? (
          <text key={`${point.key}-label`} className="console-axis-label" x={xFor(index)} y="85">
            {compactChartLabel(point.label, mode)}
          </text>
        ) : null)}
    </svg>
  );
}

function consoleModeLabel(mode: ConsoleMode) {
  if (mode === "records") {
    return "Record time signal";
  }
  if (mode === "locations") {
    return "Mapped place signal";
  }
  return "Source family signal";
}

function countRecordValues(records: readonly RecordItem[], getKey: (record: RecordItem) => string | null | undefined) {
  return records.reduce<Record<string, number>>((acc, record) => {
    const key = getKey(record);
    if (!key) {
      return acc;
    }
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
}

function recordsByYear(records: readonly RecordItem[]) {
  return records.reduce<Record<string, number>>((acc, record) => {
    if (record.year === null || record.year === undefined) {
      return acc;
    }
    const key = String(record.year);
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
}

function buildConsoleChartPoints({
  mode,
  recordsByYear,
  timelineLayers,
  sourceCounts,
  stateEntries,
  limit,
}: {
  mode: ConsoleMode;
  recordsByYear: Record<string, number>;
  timelineLayers: TimelineLayerPoint[];
  sourceCounts: Record<string, number>;
  stateEntries: readonly (readonly [string, number])[];
  limit: number;
}): ConsoleChartPoint[] {
  if (mode === "records") {
    void recordsByYear;
    void limit;
    return timelineLayers;
  }
  if (mode === "locations") {
    return stateEntries.map(([label, value]) => ({
      key: `state-${label}`,
      label,
      value,
    }));
  }
  return entriesDescending(sourceCounts, Math.min(10, limit)).map(([label, value]) => ({
    key: `source-${label}`,
    label: publicSourceLabel(label),
    value,
  }));
}

function buildTimelineLayerPoints(records: readonly RecordItem[], mapFlags: readonly MapFlagRenderItem[], targetBins: number): TimelineLayerPoint[] {
  const years = records
    .map((record) => record.year)
    .filter((year): year is number => typeof year === "number" && Number.isFinite(year))
    .sort((a, b) => a - b);
  if (!years.length) {
    return [];
  }
  const minYear = years[0];
  const maxYear = years[years.length - 1];
  const span = Math.max(1, maxYear - minYear + 1);
  const binCount = Math.min(targetBins, span);
  const bins = Array.from({ length: binCount }, (_, index) => {
    const start = Math.round(minYear + (index / binCount) * span);
    const end = Math.round(minYear + ((index + 1) / binCount) * span - 1);
    return {
      key: `year-${start}-${end}`,
      label: start === end ? String(start) : `${start}-${end}`,
      value: 0,
      mapped: 0,
      diversitySet: new Set<string>(),
    };
  });
  const binIndexForYear = (year: number) => Math.min(binCount - 1, Math.max(0, Math.floor(((year - minYear) / span) * binCount)));
  for (const record of records) {
    if (typeof record.year !== "number" || !Number.isFinite(record.year)) {
      continue;
    }
    const bin = bins[binIndexForYear(record.year)];
    bin.value += 1;
    bin.diversitySet.add(narrativeGroupLabel(record));
  }
  for (const flag of mapFlags) {
    const year = flag.record.year;
    if (typeof year !== "number" || !Number.isFinite(year)) {
      continue;
    }
    bins[binIndexForYear(year)].mapped += 1;
  }
  return bins.map(({ diversitySet, ...bin }) => ({
    ...bin,
    diversity: diversitySet.size,
  }));
}

function dashboardTrackLabel(record: RecordItem) {
  const year = record.year ? String(record.year) : "----";
  return `${dashboardTrackTitle(record, 26)} (${year})`;
}

function dashboardTrackTitle(record: RecordItem, limit: number) {
  const figure = record.canonical_figure_guess || record.canonical_figure || "";
  const rawTitle = record.title || figure || `Record ${record.record_id}`;
  const title = rawTitle
    .replace(/^\s*(?:ca\.?\s*)?\d{4}\s*[-–:]\s*/i, "")
    .replace(/\s*\/\s*\d{4}\s*$/i, "")
    .replace(/\s+/g, " ")
    .trim();
  const genericFigure = new Set(["yowie", "ghost", "apparition", "hairy man"]);
  const figureNorm = figure.trim().toLowerCase();
  const titleNorm = title.trim().toLowerCase();
  const label =
    title && titleNorm !== figureNorm && !titleNorm.startsWith("record ")
      ? title
      : figure && !genericFigure.has(figureNorm)
        ? figure
        : title || figure || `Record ${record.record_id}`;
  return truncate(label, limit);
}

function dashboardTrackMeta(record: RecordItem) {
  const year = record.year ? String(record.year) : "----";
  const source = record.publication || record.source_name || publicSourceLabel(record.source_type);
  const place = record.map_place_name || record.location_summary?.replace(/\s*:\s*(?:high|medium|low|broad).*$/i, "") || record.state_territory || "place pending";
  return `${year} / ${truncate(source, 24)} / ${truncate(place, 24)}`;
}

function trackMicroLabel(record: RecordItem) {
  const year = record.year ? String(record.year) : "----";
  const source = publicSourceLabel(record.source_type);
  return `${truncate(source, 8)} ${year}`;
}

function publicDashboardValueLabel(label: string, mode: ConsoleMode) {
  if (mode === "sources") {
    return publicSourceLabel(label);
  }
  return label.replace(/[_-]+/g, " ");
}

function narrativeGroupLabel(record: RecordItem) {
  const key = record.ontology_code || record.genre || record.canonical_figure_guess || record.canonical_figure || "other";
  if (NARRATIVE_TYPE_LABELS[key]) {
    return NARRATIVE_TYPE_LABELS[key];
  }
  const normalized = key.toLowerCase().replace(/[_-]+/g, " ");
  if (/\byow|hairy|apeman|wild ?man\b/.test(normalized)) {
    return "Hairy humanoid reports";
  }
  if (/\bghost|apparition|spirit\b/.test(normalized)) {
    return "Ghost / apparition";
  }
  if (/\bgiant|ogre\b/.test(normalized)) {
    return "Giant / ogre narratives";
  }
  if (/\bretell|adapt/.test(normalized)) {
    return "Retellings";
  }
  if (/\btradition|myth|belief\b/.test(normalized)) {
    return "Traditional narratives";
  }
  return "Other typed context";
}

function publicSourceLabel(sourceType: string | null | undefined) {
  if (!sourceType) {
    return "Public source";
  }
  return SOURCE_PUBLIC_LABELS[sourceType] ?? SOURCE_TONE[sourceType]?.label ?? sourceType.replace(/[_-]+/g, " ");
}

function dashboardTrackSample(data: FrontendData, limit = 14) {
  const pool = data.records.filter((record) => record.relevance_code !== "noise");
  const byYear = [...pool].sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999) || a.record_id - b.record_id);
  const selected: RecordItem[] = [];
  const seen = new Set<number>();
  const add = (record: RecordItem | undefined) => {
    if (record && !seen.has(record.record_id) && selected.length < limit) {
      selected.push(record);
      seen.add(record.record_id);
    }
  };

  const firstBy = (keyFn: (record: RecordItem) => string | null | undefined, limit: number) => {
    const keys = new Set<string>();
    for (const record of byYear) {
      const key = keyFn(record);
      if (!key || keys.has(key)) {
        continue;
      }
      keys.add(key);
      add(record);
      if (keys.size >= limit || selected.length >= limit) {
        break;
      }
    }
  };

  const figureOf = (record: RecordItem) => record.canonical_figure_guess || record.canonical_figure || record.title || "uncoded";
  const nonDominant = byYear.filter((record) => !/^yowie$/i.test(figureOf(record)));
  for (const record of nonDominant) {
    add(record);
    if (selected.length >= Math.min(14, limit)) {
      break;
    }
  }

  firstBy((record) => figureOf(record), 10);
  firstBy((record) => record.source_type || record.source_name, 5);

  for (const code of Object.keys(STATE_NAMES)) {
    add(byYear.find((record) => record.state_territory === code));
  }

  for (const band of data.date_bands) {
    add(byYear.find((record) => record.date_band === band.id));
  }

  for (const record of byYear) {
    add(record);
  }

  return selected;
}

function aggregateYearValues(entries: readonly (readonly [number, number])[], targetBins: number) {
  if (entries.length <= targetBins) {
    return entries.map(([year, value]) => [String(year), value] as const);
  }
  const minYear = entries[0]?.[0] ?? 0;
  const maxYear = entries[entries.length - 1]?.[0] ?? minYear;
  const span = Math.max(1, maxYear - minYear + 1);
  const binCount = Math.min(targetBins, span);
  const bins = Array.from({ length: binCount }, (_, index) => ({
    start: Math.round(minYear + (index / binCount) * span),
    end: Math.round(minYear + ((index + 1) / binCount) * span - 1),
    value: 0,
  }));
  for (const [year, value] of entries) {
    const index = Math.min(binCount - 1, Math.max(0, Math.floor(((year - minYear) / span) * binCount)));
    bins[index].value += value;
  }
  return bins.map((bin) => [`${bin.start}-${bin.end}`, bin.value] as const);
}

function SignalSquare({ records }: { records: RecordItem[] }) {
  const nodes = records.slice(0, 14).map((record, index) => {
    const leftColumn = index % 2 === 0;
    return {
      record,
      x: leftColumn ? 12 + (index % 3) * 7 : 57 + (index % 3) * 9,
      y: 12 + index * 5.7,
      anchorX: 50,
      anchorY: 50 + ((index % 5) - 2) * 7,
    };
  });

  return (
    <section className="signal-square">
      <svg viewBox="0 0 100 100" className="signal-svg" role="img" aria-label="Record signal network">
        <rect x="36" y="42" width="28" height="16" className="signal-core" />
        <text x="39" y="51" className="signal-core-text">
          ARCH
        </text>
        {nodes.map((node) => (
          <line
            key={`line-${node.record.record_id}`}
            className="signal-line"
            x1={node.x + 8}
            y1={node.y + 2}
            x2={node.anchorX}
            y2={node.anchorY}
          />
        ))}
        {nodes.map((node) => (
          <g key={node.record.record_id}>
            <rect x={node.x} y={node.y} width="15" height="4.3" className="slot-box" />
            <rect x={node.x + 2} y={node.y + 0.9} width="10" height="2.5" className="slot-fill" />
            <text x={node.x + 16.5} y={node.y + 3.6} className="slot-label">
              SLOT_{String(node.record.record_id).padStart(2, "0")}
            </text>
          </g>
        ))}
      </svg>
      <div className="square-caption">
        <span>RECORD SIGNAL</span>
        <b>{records.length}</b>
      </div>
    </section>
  );
}

function MetricTile({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <div className="metric-tile">
      <span>{label}</span>
      <b>{numberFormat(value)}</b>
      <small>{detail}</small>
    </div>
  );
}

function Dial({ title, values }: { title: string; values: Record<string, number> }) {
  const topEntries = entriesDescending(values, 4);
  return (
    <div className="dial-module">
      <span className="tiny-label">{title}</span>
      <div className="dial-ring" style={{ "--dial": conicGradient(values) } as CSSProperties}>
        <div />
      </div>
      <div className="dial-list">
        {topEntries.map(([label, count]) => (
          <span key={label}>
            {truncate(label, 13)} <b>{count}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

function MiniSpark({ values }: { values: Record<string, number> }) {
  const entries = Object.entries(values).sort(([a], [b]) => Number(a) - Number(b));
  const max = Math.max(...entries.map(([, value]) => value), 1);
  return (
    <div className="mini-spark" aria-label="Year signal">
      {entries.map(([year, value]) => (
        <span key={year} style={{ "--bar": `${Math.max(10, (value / max) * 100)}%` } as CSSProperties} title={`${year}: ${value}`} />
      ))}
    </div>
  );
}

function Waveform({ records }: { records: RecordItem[] }) {
  const sorted = [...records].sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999));
  const points = sorted.map((record, index) => {
    const x = 8 + (index / Math.max(sorted.length - 1, 1)) * 184;
    const year = record.year ?? 0;
    const y = 48 - ((year % 37) / 37) * 36;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <div className="wave-module">
      <span className="tiny-label">SIGNAL</span>
      <svg viewBox="0 0 200 58" role="img" aria-label="Record waveform">
        <polyline className="wave-shadow" points={points.join(" ")} />
        <polyline className="wave-line" points={points.join(" ")} />
      </svg>
    </div>
  );
}

function RecordLine({ record }: { record: RecordItem }) {
  const sensitive = record.ethics_flag === "caution_indigenous_knowledge";
  return (
    <div className={sensitive ? "record-line caution" : "record-line"}>
      <span>{record.year ?? "----"}</span>
      <b>{truncate(record.canonical_figure_guess || record.canonical_figure, 18)}</b>
      <em>{truncate(record.location_summary || record.publication, 32)}</em>
    </div>
  );
}

function sourceTone(record: RecordItem) {
  return SOURCE_TONE[record.source_type ?? ""] ?? { label: "SOURCE", className: "source-tone-default" };
}

const HISTORICAL_PUBLICATION_PATTERN =
  /\b(article|courier|post|herald|argus|bulletin|times|mercury|gazette|advertiser|chronicle|examiner|star|mail|mirror|telegraph|age|leader|news|budget|advocate|journal|guardian|free press|penny post|press)\b/i;

function mapSourceTone(record: RecordItem) {
  const text = [record.source_name, record.source_type, record.publication, record.title, record.url].filter(Boolean).join(" ");
  const lower = text.toLowerCase();
  if (/public_domain|gutenberg|wikisource|sacred_texts/.test(lower)) {
    return { label: "PUBLIC DOMAIN", className: "source-tone-candidate" };
  }
  if (/repository|trove|newspaper|magazine/.test(lower)) {
    return { label: "REPOSITORY", className: "source-tone-archive" };
  }
  if (lower.includes("abc")) {
    return { label: "MEDIA", className: "source-tone-media" };
  }
  if (lower.includes("parks victoria") || lower.includes("museum") || lower.includes("library") || lower.includes("catalogue")) {
    return { label: "INSTITUTIONAL", className: "source-tone-institutional" };
  }
  if (lower.includes("australian yowie research")) {
    if ((record.year && record.year < 1970) || HISTORICAL_PUBLICATION_PATTERN.test(text)) {
      return { label: "AYR HISTORICAL", className: "source-tone-ayr-historical" };
    }
    return { label: "AYR WITNESS", className: "source-tone-ayr-witness" };
  }
  if (record.source_type === "academic_metadata") {
    return { label: "ACADEMIC", className: "source-tone-academic" };
  }
  if (record.source_type === "internet_archive_metadata") {
    return { label: "ARCHIVE", className: "source-tone-archive" };
  }
  if (record.source_type === "seeded_public_web") {
    return { label: "PUBLIC WEB", className: "source-tone-seeded-web" };
  }
  return sourceTone(record);
}

function recordDisplayTitle(record: RecordItem) {
  return record.canonical_figure_guess || record.canonical_figure || record.title || "Uncoded public record";
}

function isSummaryOnlyRecord(record: RecordItem) {
  const values = [record.ethics_flag, record.publicness_code, record.publicness_level, record.ingestion_status].filter(Boolean).join(" ");
  return /summary|restricted|caution_indigenous_knowledge|sensitive/i.test(values);
}

function recordBody(record: RecordItem) {
  if (isSummaryOnlyRecord(record)) {
    const source = record.publication || record.source_name || "a public source";
    const date = record.date_published || (record.year ? String(record.year) : "date unknown");
    return `Summary-only public record from ${source} (${date}). This card keeps the display at metadata level because the item carries publicness or sensitivity restrictions.`;
  }
  if (record.snippet) {
    return record.snippet;
  }
  const figure = recordDisplayTitle(record);
  const source = record.publication || record.source_name || "a public source";
  const date = record.date_published || (record.year ? String(record.year) : "an undated record");
  return `Public record note for ${figure}, recorded in ${source} (${date}). This card is a review surface: source voice, relevance, location, and publicness still require human checking before interpretation.`;
}

type RecordNavigationContext = {
  records: RecordItem[];
  currentIndex: number;
  regionLabel: string;
};

function recordNavigationContext(derived: FrontendDerivedData, record: RecordItem): RecordNavigationContext {
  const state = record.has_strict_map_point ? record.state_territory : null;
  const stateRecords = state ? derived.navigationRecordsByState.get(state) ?? [] : [];
  const records = stateRecords.length ? stateRecords : derived.sortedRecords;
  const currentIndex = Math.max(
    0,
    records.findIndex((item) => item.record_id === record.record_id),
  );
  return {
    records,
    currentIndex,
    regionLabel: state ? STATE_NAMES[state] ?? state : "archive",
  };
}

function RecordCardOverlay({
  record,
  navigation,
  onClose,
  onNavigate,
}: {
  record: RecordItem;
  navigation: RecordNavigationContext | null;
  onClose: () => void;
  onNavigate: (direction: 1 | -1) => void;
}) {
  const tone = mapSourceTone(record);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const location = record.location_summary || "location unverified";
  const sourceName = record.source_name || record.publication || "public source";
  const sourceClass = tone.className;
  const year = record.year ?? "----";
  const body = recordBody(record);
  const canNavigate = Boolean(navigation && navigation.records.length > 1);
  const navPosition = navigation ? `${navigation.currentIndex + 1} / ${navigation.records.length}` : "1 / 1";
  const titleId = `record-card-title-${record.record_id}`;

  useEffect(() => {
    closeButtonRef.current?.focus();
  }, [record.record_id]);

  return (
    <div className="record-overlay" role="presentation" onClick={onClose}>
      <div className="record-card-shell" onClick={(event) => event.stopPropagation()}>
        {canNavigate ? (
          <>
            <button
              className="record-card-nav record-card-nav-prev"
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onNavigate(-1);
              }}
              aria-label={`Previous record in ${navigation?.regionLabel ?? "current region"}`}
            >
              &lt;
            </button>
            <button
              className="record-card-nav record-card-nav-next"
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onNavigate(1);
              }}
              aria-label={`Next record in ${navigation?.regionLabel ?? "current region"}`}
            >
              &gt;
            </button>
          </>
        ) : null}
        <article
          className={`record-card ${sourceClass}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
        >
        <section className="record-card-table" aria-label="Record metadata">
          <div className="record-card-table-top">
            <span>aus humanoid record</span>
            <span>{navigation?.regionLabel ?? "archive"} / {navPosition}</span>
            <button ref={closeButtonRef} type="button" onClick={onClose} aria-label="Close record card">
              CLOSE
            </button>
          </div>
          <div className="record-card-grid">
            <div>
              <span>REGION</span>
              <b>{truncate(location, 42)}</b>
            </div>
            <div>
              <span>SOURCE</span>
              <b>{truncate(sourceName, 36)}</b>
            </div>
            <div>
              <span>TYPE</span>
              <b>{tone.label}</b>
            </div>
            <div>
              <span>PUBLICNESS</span>
              <b>{record.publicness_code || record.publicness_level || "public review"}</b>
            </div>
            <div>
              <span>STATUS</span>
              <b>{record.relevance_code || "needs_review"}</b>
            </div>
          </div>
        </section>

        <section className="record-card-title-block">
          <div className="record-card-year">{year}</div>
          <h2 id={titleId}>{recordDisplayTitle(record)}</h2>
        </section>

        <section className="record-card-body">
          <span className="record-card-body-mark">RECORD NOTE</span>
          <p>{body}</p>
          <footer>
            <span>{record.date_published || "date unknown"}</span>
            <span>{record.genre || record.source_voice || "source voice pending"}</span>
            {record.url ? (
              <a href={record.url} target="_blank" rel="noreferrer">
                OPEN SOURCE
              </a>
            ) : (
              <span>NO PUBLIC URL</span>
            )}
          </footer>
        </section>
        </article>
      </div>
    </div>
  );
}
