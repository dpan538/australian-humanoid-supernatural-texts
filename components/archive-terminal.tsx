"use client";

import { CSSProperties, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import Link from "next/link";
import { createTimeline, stagger } from "animejs";
import type { Timeline } from "animejs";
import type { DateBand, FrontendData, MapFlagItem, RecordItem } from "@/lib/types";
import { MAP_BOUNDARY_SOURCE, MAP_VIEWBOX, STATE_SHAPES, TERRAIN_TILES } from "@/lib/au-map-data";
import { figureProfileFor } from "@/lib/figure-profiles";
import type { FigureProfile } from "@/lib/figure-profiles";
import { FRONTEND_DATA_SCHEMA, FRONTEND_DATA_URL } from "@/lib/frontend-data";
import { SourceView } from "@/components/source/source-view";
import { DisplayControls } from "@/components/display-controls";
import { SOURCE_FAMILY_STYLES, displaySourceType, sourceFamilyId, type SourceFamilyId } from "@/lib/source-view-data";

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
const SOURCE_CLASS_BY_FAMILY: Record<SourceFamilyId, string> = {
  repository: "source-tone-archive",
  modern_web: "source-tone-web",
  public_domain: "source-tone-candidate",
  institutions: "source-tone-institutional",
  academic: "source-tone-academic",
  community: "source-tone-community",
  other: "source-tone-default",
};

type SourceFamilyChartItem = {
  id: SourceFamilyId;
  label: string;
  color: string;
  strokeColor: string;
  fillColor: string;
  softColor: string;
  className: string;
};

const SOURCE_FAMILIES: SourceFamilyChartItem[] = (Object.keys(SOURCE_FAMILY_STYLES) as SourceFamilyId[]).map((id) => ({
  id,
  label: SOURCE_FAMILY_STYLES[id].label,
  color: SOURCE_FAMILY_STYLES[id].color,
  strokeColor: SOURCE_FAMILY_STYLES[id].stroke,
  fillColor: SOURCE_FAMILY_STYLES[id].fill,
  softColor: SOURCE_FAMILY_STYLES[id].soft,
  className: SOURCE_CLASS_BY_FAMILY[id],
}));

const SOURCE_FAMILY_BY_ID = new Map<SourceFamilyId, SourceFamilyChartItem>(
  SOURCE_FAMILIES.map((family) => [family.id, family] as const),
);

type MatrixCell = {
  bandId: string;
  bandLabel: string;
  value: number;
};
type NarrativePeriodRow = {
  label: string;
  values: MatrixCell[];
};
type AnnualDensityPoint = {
  year: number;
  total: number;
  mapped: number;
};
type PeriodBoxPlotStat = {
  band: DateBand;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  total: number;
  mapped: number;
};
type DensityChartMode = "temporal" | "distribution" | "figures" | "sources" | "regions" | "cross";
type DensityChartDatum = {
  key: string;
  label: string;
  value: number;
  secondary?: number;
};
type DensityCrossRow = {
  figure: string;
  values: MatrixCell[];
  total: number;
};
type FigureDensityItem = {
  slug: string;
  label: string;
  profile: FigureProfile;
  records: RecordItem[];
  mappedCount: number;
  dateSpan: string;
  earliestYear: number | null;
  latestYear: number | null;
  topSourceFamily: string;
  topRegion: string;
  topNarrativeFamily: string;
  note: string;
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
  id: SourceFamilyId;
  label: string;
  color: string;
  strokeColor: string;
  fillColor: string;
  softColor: string;
  count: number;
  mappedCount: number;
  sourceOrgCount: number;
  periodCoverage: number;
  dominantBandId: string | null;
  dominantBandLabel: string;
  dominantBandShare: number;
  narrativeSpread: number;
  jurisdictionSpread: number;
  yearStart: number | null;
  yearEnd: number | null;
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
  id: SourceFamilyId;
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
  const source = sourceFamilyFor(record.source_type).label;
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
  if (/repository|archive/.test(normalized)) {
    return "source-repository";
  }
  if (/public-domain|book|gutenberg/.test(normalized)) {
    return "source-public-domain";
  }
  if (/modern|web/.test(normalized)) {
    return "source-modern-web";
  }
  if (/institution/.test(normalized)) {
    return "source-institution";
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
  if (sourceClass === "source-repository") {
    return SOURCE_FAMILY_STYLES.repository.stroke;
  }
  if (sourceClass === "source-public-domain") {
    return SOURCE_FAMILY_STYLES.public_domain.stroke;
  }
  if (sourceClass === "source-modern-web") {
    return SOURCE_FAMILY_STYLES.modern_web.stroke;
  }
  if (sourceClass === "source-institution") {
    return SOURCE_FAMILY_STYLES.institutions.stroke;
  }
  if (sourceClass === "source-academic") {
    return SOURCE_FAMILY_STYLES.academic.stroke;
  }
  if (sourceClass === "source-community") {
    return SOURCE_FAMILY_STYLES.community.stroke;
  }
  return SOURCE_FAMILY_STYLES.other.stroke;
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

  return prepareMapFlagPresentation(flags, data.date_bands);
}

function prepareMapFlagPresentation(flags: MapFlagRenderItem[], dateBands: readonly DateBand[]) {
  const collisionGroups = new Map<string, MapFlagRenderItem[]>();

  for (const flag of flags) {
    flag.growthBucket = chronologicalGrowthBucket(flag, dateBands);
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

function chronologicalGrowthBucket(flag: MapFlagRenderItem, dateBands: readonly DateBand[]) {
  const bandIndex = dateBands.findIndex((band) => {
    if (flag.record.date_band === band.id) {
      return true;
    }
    return (
      typeof flag.year === "number" &&
      typeof band.start === "number" &&
      typeof band.end === "number" &&
      flag.year >= band.start &&
      flag.year <= band.end
    );
  });
  if (bandIndex >= 0) {
    return bandIndex;
  }
  return Math.max(0, dateBands.length - 1);
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
  const counts = new Map<SourceFamilyId, number>();
  for (const flag of mapFlags) {
    const family = sourceFamilyFor(flag.record.source_type);
    counts.set(family.id, (counts.get(family.id) ?? 0) + 1);
  }

  return SOURCE_FAMILIES.map((family) => ({
    id: family.id,
    label: family.label,
    className: family.className,
    count: counts.get(family.id) ?? 0,
  })).filter((group) => group.count > 0);
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
  return dateBands.find((band) => (
    typeof band.start === "number" &&
    typeof band.end === "number" &&
    year >= band.start &&
    year <= band.end
  ))?.id ?? "undated";
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

    const orderedBuckets = [...bucketGroups.keys()].map((bucket) => Number(bucket)).sort((a, b) => a - b);
    for (const bucket of orderedBuckets) {
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
          aria-label="Public record map of Australia by state and territory"
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
  const densityViewRef = useRef<HTMLDivElement | null>(null);
  const [selectedFigureIndex, setSelectedFigureIndex] = useState<number | null>(null);
  const periodBands = useMemo(() => data.date_bands.filter((band) => band.id !== "undated"), [data.date_bands]);
  const maxRecords = Math.max(...periodBands.map((band) => band.record_count), 1);
  const maxQueries = Math.max(...periodBands.map((band) => band.planned_query_count), 1);
  const mappedByBand = useMemo(() => buildMappedCountByDateBand(derived.mapFlags), [derived.mapFlags]);
  const annualSeries = useMemo(() => buildAnnualDensitySeries(data.records, derived.mapFlags), [data.records, derived.mapFlags]);
  const boxStats = useMemo(() => buildPeriodBoxPlotStats(periodBands, data.records, derived.mapFlags), [periodBands, data.records, derived.mapFlags]);
  const figureDensityItems = useMemo(() => buildFigureDensityItems(data.records, derived.mapFlags), [data.records, derived.mapFlags]);
  const figureFrequency = useMemo(() => figureDensityItems.slice(0, 8).map((figure) => ({
    key: figure.slug,
    label: figure.label,
    value: figure.records.length,
    secondary: figure.mappedCount,
  })), [figureDensityItems]);
  const sourceComposition = useMemo(() => buildSourceComposition(data.records, derived.mapFlags), [data.records, derived.mapFlags]);
  const regionConcentration = useMemo(() => buildRegionConcentration(data.records, derived.mapFlags), [data.records, derived.mapFlags]);
  const figurePeriodMatrix = useMemo(() => buildFigurePeriodMatrix(figureDensityItems, periodBands), [figureDensityItems, periodBands]);
  const locationHealth = {
    map_flags: derived.mapFlags.length,
    broad_or_review: Math.max(0, data.summary.record_count - derived.mapFlags.length),
    undated_records: derived.undatedRecordCount,
    locations_total: data.summary.location_count,
  };
  const selectedFigure = selectedFigureIndex === null ? null : figureDensityItems[selectedFigureIndex] ?? null;

  useDensityMotion(densityViewRef);

  useEffect(() => {
    function resetDensityScroll() {
      densityViewRef.current?.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
    window.addEventListener("archive-display-change", resetDensityScroll);
    return () => window.removeEventListener("archive-display-change", resetDensityScroll);
  }, []);

  return (
    <div className="density-view" ref={densityViewRef}>
      <header className="density-header">
        <div>
          <span>TIME DENSITY</span>
          <p>Density shows public-text record distribution and source coverage. It is not a claim about real-world frequency.</p>
        </div>
        <b>
          {data.summary.earliest_year}-{data.summary.latest_year} / {numberFormat(data.summary.record_count)} PUBLIC RECORDS / {numberFormat(data.summary.mapped_record_count)} MAPPED
        </b>
      </header>
      <div className="density-bands">
        {periodBands.map((band) => (
          <DensityBand
            key={band.id}
            band={band}
            maxRecords={maxRecords}
            maxQueries={maxQueries}
            mappedCount={mappedByBand[band.id] ?? 0}
            firstRecord={derived.firstRecordByDateBand.get(band.id) ?? null}
            onSelectRecord={onSelectRecord}
          />
        ))}
      </div>
      <DensityChartPanel
        annualSeries={annualSeries}
        boxStats={boxStats}
        figureFrequency={figureFrequency}
        sourceComposition={sourceComposition}
        regionConcentration={regionConcentration}
        figurePeriodMatrix={figurePeriodMatrix}
        periodBands={periodBands}
      />
      <div className="density-aux-grid">
        <DensityMetricPanel title="LOCATION HEALTH" values={locationHealth} />
        <DensityFigureRail figures={figureDensityItems} onSelectFigure={setSelectedFigureIndex} />
      </div>
      {selectedFigure ? (
        <FigureCardOverlay
          figures={figureDensityItems}
          figure={selectedFigure}
          figureIndex={selectedFigureIndex ?? 0}
          onClose={() => setSelectedFigureIndex(null)}
          onNavigate={(direction) => {
            setSelectedFigureIndex((current) => {
              const index = current ?? 0;
              return (index + direction + figureDensityItems.length) % figureDensityItems.length;
            });
          }}
        />
      ) : null}
    </div>
  );
}

function DensityBand({
  band,
  maxRecords,
  maxQueries,
  mappedCount,
  firstRecord,
  onSelectRecord,
}: {
  band: DateBand;
  maxRecords: number;
  maxQueries: number;
  mappedCount: number;
  firstRecord: RecordItem | null;
  onSelectRecord: (record: RecordItem) => void;
}) {
  const recordWidth = Math.max(3, (band.record_count / maxRecords) * 100);
  const queryWidth = Math.max(3, (band.planned_query_count / maxQueries) * 100);
  const mappedShare = formatPercent(mappedCount, band.record_count);
  return (
    <section
      className={firstRecord ? "density-band clickable-record" : "density-band"}
      onClick={() => {
        if (firstRecord) {
          onSelectRecord(firstRecord);
        }
      }}
      onKeyDown={(event) => {
        if (firstRecord && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onSelectRecord(firstRecord);
        }
      }}
      role={firstRecord ? "button" : undefined}
      tabIndex={firstRecord ? 0 : undefined}
      aria-label={firstRecord ? `Open sample record for ${band.label}` : undefined}
    >
      <div className="band-meta">
        <span>{band.label}</span>
        <b>{numberFormat(band.record_count)}</b>
        <small>{numberFormat(mappedCount)} mapped / {mappedShare}</small>
      </div>
      <div className="density-band-bars" aria-hidden="true">
        <i className="density-bar-fill" style={{ "--bar-width": `${recordWidth}%` } as CSSProperties} title={`${band.label}: ${numberFormat(band.record_count)} public records`} />
        <em className="density-bar-fill" style={{ "--bar-width": `${queryWidth}%` } as CSSProperties} title={`${band.label}: ${numberFormat(band.planned_query_count)} planned queries`} />
      </div>
      <dl className="density-band-stats">
        <div>
          <dt>Public records</dt>
          <dd>{numberFormat(band.record_count)}</dd>
        </div>
        <div>
          <dt>Planned queries</dt>
          <dd>{numberFormat(band.planned_query_count)}</dd>
        </div>
      </dl>
      {firstRecord ? <span className="density-band-action">OPEN SAMPLE</span> : null}
    </section>
  );
}

const DENSITY_CHART_MODES: Array<{ id: DensityChartMode; label: string }> = [
  { id: "temporal", label: "Temporal" },
  { id: "distribution", label: "Distribution" },
  { id: "figures", label: "Figures" },
  { id: "sources", label: "Sources" },
  { id: "regions", label: "Regions" },
  { id: "cross", label: "Cross-analysis" },
];

function DensityChartPanel({
  annualSeries,
  boxStats,
  figureFrequency,
  sourceComposition,
  regionConcentration,
  figurePeriodMatrix,
  periodBands,
}: {
  annualSeries: AnnualDensityPoint[];
  boxStats: PeriodBoxPlotStat[];
  figureFrequency: DensityChartDatum[];
  sourceComposition: DensityChartDatum[];
  regionConcentration: DensityChartDatum[];
  figurePeriodMatrix: DensityCrossRow[];
  periodBands: DateBand[];
}) {
  const [mode, setMode] = useState<DensityChartMode>("temporal");
  const panelRef = useRef<HTMLElement | null>(null);

  useDensityPanelMotion(panelRef, mode);

  return (
    <section className="density-chart-panel" ref={panelRef} aria-label="Density charts">
      <div className="density-chart-switcher" role="tablist" aria-label="Density chart mode">
        {DENSITY_CHART_MODES.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={mode === item.id}
            className={mode === item.id ? "is-active" : undefined}
            onClick={() => setMode(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {mode === "temporal" ? <DensityAnnualLineChart series={annualSeries} /> : null}
      {mode === "distribution" ? <DensityPeriodBoxPlot stats={boxStats} /> : null}
      {mode === "figures" ? <DensityRankedBarChart title="FIGURE FREQUENCY" subtitle="Top public-text figure labels" data={figureFrequency} secondaryLabel="mapped" /> : null}
      {mode === "sources" ? <DensityRankedBarChart title="SOURCE COMPOSITION" subtitle="Source families shaping the archive" data={sourceComposition} secondaryLabel="mapped" /> : null}
      {mode === "regions" ? <DensityRankedBarChart title="REGIONAL CONCENTRATION" subtitle="Public and mapped records by state or territory" data={regionConcentration} secondaryLabel="mapped" /> : null}
      {mode === "cross" ? <DensityFigurePeriodHeatmap rows={figurePeriodMatrix} periods={periodBands} /> : null}
    </section>
  );
}

function DensityAnnualLineChart({ series }: { series: AnnualDensityPoint[] }) {
  const width = 1500;
  const height = 240;
  const margin = { top: 18, right: 36, bottom: 38, left: 60 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const minYear = series[0]?.year ?? 0;
  const maxYear = series[series.length - 1]?.year ?? minYear + 1;
  const maxValue = Math.max(...series.map((point) => Math.max(point.total, point.mapped)), 1);
  const xFor = (year: number) => margin.left + ((year - minYear) / Math.max(1, maxYear - minYear)) * innerWidth;
  const yFor = (value: number) => margin.top + innerHeight - (value / maxValue) * innerHeight;
  const publicPath = series.map((point) => `${xFor(point.year)},${yFor(point.total)}`).join(" ");
  const mappedPath = series.map((point) => `${xFor(point.year)},${yFor(point.mapped)}`).join(" ");
  const yearTicks = buildLinearTicks(minYear, maxYear, 5).map((tick) => Math.round(tick));
  const valueTicks = buildLinearTicks(0, maxValue, 5).map((tick) => Math.round(tick));

  return (
    <article className="density-chart-card">
      <header>
        <span>ANNUAL TREND</span>
        <b>Dated public records by year</b>
      </header>
      <svg className="density-line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Annual public record trend line chart">
        {valueTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line className="density-chart-grid" x1={margin.left} x2={width - margin.right} y1={yFor(tick)} y2={yFor(tick)} />
            <text className="density-chart-axis" x={margin.left - 10} y={yFor(tick) + 4} textAnchor="end">
              {tick}
            </text>
          </g>
        ))}
        {yearTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line className="density-chart-tick" x1={xFor(tick)} x2={xFor(tick)} y1={height - margin.bottom} y2={height - margin.bottom + 6} />
            <text className="density-chart-axis" x={xFor(tick)} y={height - 16} textAnchor="middle">
              {tick}
            </text>
          </g>
        ))}
        <line className="density-chart-axis-line" x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} />
        <line className="density-chart-axis-line" x1={margin.left} x2={margin.left} y1={margin.top} y2={height - margin.bottom} />
        <polyline className="density-line-public density-chart-path" points={publicPath} fill="none" />
        <polyline className="density-line-mapped density-chart-path" points={mappedPath} fill="none" />
      </svg>
      <div className="density-chart-legend">
        <span><i className="legend-public" /> public records</span>
        <span><i className="legend-mapped" /> mapped records</span>
      </div>
    </article>
  );
}

function DensityPeriodBoxPlot({ stats }: { stats: PeriodBoxPlotStat[] }) {
  const width = 1500;
  const rowHeight = 30;
  const margin = { top: 22, right: 60, bottom: 34, left: 156 };
  const height = margin.top + margin.bottom + stats.length * rowHeight;
  const innerWidth = width - margin.left - margin.right;
  const maxValue = Math.max(...stats.map((stat) => stat.max), 1);
  const xFor = (value: number) => margin.left + (value / maxValue) * innerWidth;
  const ticks = buildLinearTicks(0, maxValue, 5).map((tick) => Math.round(tick));

  return (
    <article className="density-chart-card">
      <header>
        <span>PERIOD DISTRIBUTION</span>
        <b>Per-year record counts inside each band</b>
      </header>
      <svg className="density-box-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Period distribution box plot">
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="density-chart-grid" x1={xFor(tick)} x2={xFor(tick)} y1={margin.top - 8} y2={height - margin.bottom} />
            <text className="density-chart-axis" x={xFor(tick)} y={height - 12} textAnchor="middle">
              {tick}
            </text>
          </g>
        ))}
        {stats.map((stat, index) => {
          const y = margin.top + index * rowHeight + rowHeight / 2;
          return (
            <g key={stat.band.id}>
              <text className="density-box-label" x={margin.left - 14} y={y + 5} textAnchor="end">
                {stat.band.label}
              </text>
              <line className="density-box-whisker" x1={xFor(stat.min)} x2={xFor(stat.max)} y1={y} y2={y} />
              <line className="density-box-cap" x1={xFor(stat.min)} x2={xFor(stat.min)} y1={y - 8} y2={y + 8} />
              <line className="density-box-cap" x1={xFor(stat.max)} x2={xFor(stat.max)} y1={y - 8} y2={y + 8} />
              <rect className="density-box-rect density-box" x={xFor(stat.q1)} y={y - 10} width={Math.max(2, xFor(stat.q3) - xFor(stat.q1))} height="20" />
              <line className="density-box-median" x1={xFor(stat.median)} x2={xFor(stat.median)} y1={y - 12} y2={y + 12} />
              <text className="density-box-count" x={width - margin.right} y={y + 5} textAnchor="end">
                {numberFormat(stat.total)}
              </text>
            </g>
          );
        })}
      </svg>
    </article>
  );
}

function DensityRankedBarChart({
  title,
  subtitle,
  data,
  secondaryLabel,
}: {
  title: string;
  subtitle: string;
  data: DensityChartDatum[];
  secondaryLabel?: string;
}) {
  const width = 1500;
  const rowHeight = 38;
  const margin = { top: 26, right: 360, bottom: 42, left: 330 };
  const height = margin.top + margin.bottom + Math.max(1, data.length) * rowHeight;
  const maxValue = Math.max(...data.map((row) => Math.max(row.value, row.secondary ?? 0)), 1);
  const xFor = (value: number) => margin.left + (value / maxValue) * (width - margin.left - margin.right);
  const valueLabelX = width - 32;
  const ticks = buildLinearTicks(0, maxValue, 5).map((tick) => Math.round(tick));

  return (
    <article className="density-chart-card density-chart-card-main">
      <header>
        <span>{title}</span>
        <b>{subtitle}</b>
      </header>
      <svg className="density-bar-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title} ranked bar chart`}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="density-chart-grid" x1={xFor(tick)} x2={xFor(tick)} y1={margin.top - 8} y2={height - margin.bottom} />
            <text className="density-chart-axis" x={xFor(tick)} y={height - 12} textAnchor="middle">
              {tick}
            </text>
          </g>
        ))}
        {data.map((row, index) => {
          const y = margin.top + index * rowHeight;
          const secondaryWidth = xFor(row.secondary ?? 0) - margin.left;
          const primaryWidth = xFor(row.value) - margin.left;
          return (
            <g key={row.key}>
              <text className="density-box-label" x={margin.left - 20} y={y + 25} textAnchor="end">
                {truncate(row.label, 22)}
              </text>
              {row.secondary ? (
                <rect className="density-bar-secondary density-bar-fill" x={margin.left} y={y + 18} width={Math.max(1, secondaryWidth)} height="8">
                  <title>{`${row.label}: ${numberFormat(row.secondary)} ${secondaryLabel ?? "secondary records"}`}</title>
                </rect>
              ) : null}
              <rect className="density-bar-primary density-bar-fill" x={margin.left} y={y + 5} width={Math.max(1, primaryWidth)} height="13">
                <title>{`${row.label}: ${numberFormat(row.value)} public records`}</title>
              </rect>
              <text className="density-box-count" x={valueLabelX} y={y + 22} textAnchor="end">
                {numberFormat(row.value)}
                {typeof row.secondary === "number" ? ` / ${numberFormat(row.secondary)} ${secondaryLabel ?? ""}` : ""}
              </text>
            </g>
          );
        })}
      </svg>
    </article>
  );
}

function DensityFigurePeriodHeatmap({ rows, periods }: { rows: DensityCrossRow[]; periods: DateBand[] }) {
  const width = 1500;
  const cellWidth = 190;
  const rowHeight = 26;
  const margin = { top: 42, right: 62, bottom: 22, left: 220 };
  const height = margin.top + margin.bottom + Math.max(1, rows.length) * rowHeight;
  const maxValue = Math.max(...rows.flatMap((row) => row.values.map((cell) => cell.value)), 1);

  return (
    <article className="density-chart-card density-chart-card-main">
      <header>
        <span>CROSS-ANALYSIS</span>
        <b>Top figures across archive periods</b>
      </header>
      <svg className="density-heatmap-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Figure by period heatmap">
        {periods.map((period, index) => (
          <text key={period.id} className="density-chart-axis" x={margin.left + index * cellWidth + cellWidth / 2} y="24" textAnchor="middle">
            {period.label.replace("present", "now")}
          </text>
        ))}
        {rows.map((row, rowIndex) => {
          const y = margin.top + rowIndex * rowHeight;
          return (
            <g key={row.figure}>
              <text className="density-box-label" x={margin.left - 14} y={y + 19} textAnchor="end">
                {truncate(row.figure, 20)}
              </text>
              {periods.map((period, columnIndex) => {
                const value = row.values.find((cell) => cell.bandId === period.id)?.value ?? 0;
                const intensity = value / maxValue;
                return (
                  <g key={`${row.figure}-${period.id}`}>
                    <rect
                      className="density-heatmap-cell density-box"
                      x={margin.left + columnIndex * cellWidth + 5}
                      y={y + 3}
                      width={cellWidth - 10}
                      height="18"
                      style={{ "--cell-opacity": String(0.14 + intensity * 0.78) } as CSSProperties}
                    >
                      <title>{`${row.figure}, ${period.label}: ${numberFormat(value)} records`}</title>
                    </rect>
                    {value > 0 ? (
                      <text className="density-heatmap-value" x={margin.left + columnIndex * cellWidth + cellWidth / 2} y={y + 17} textAnchor="middle">
                        {numberFormat(value)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
              <text className="density-box-count" x={width - margin.right} y={y + 19} textAnchor="end">
                {numberFormat(row.total)}
              </text>
            </g>
          );
        })}
      </svg>
    </article>
  );
}

function DensityMetricPanel({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = entriesDescending(values, 5);
  const max = Math.max(...entries.map(([, value]) => value), 1);

  return (
    <section className="density-metric">
      <span className="tiny-label">{title}</span>
      <div className="density-metric-bars">
        {entries.map(([label, value]) => (
          <div key={label} className="density-metric-row">
            <span>{truncate(label, 18)}</span>
            <i style={{ "--metric-width": `${Math.max(8, (value / max) * 100)}%` } as CSSProperties} />
            <b>{value}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function DensityFigureRail({
  figures,
  onSelectFigure,
}: {
  figures: FigureDensityItem[];
  onSelectFigure: (index: number) => void;
}) {
  return (
    <section className="density-figure-rail">
      <span className="tiny-label">FIGURE MIX</span>
      <div>
        {figures.slice(0, 8).map((figure, index) => (
          <button
            key={figure.slug}
            type="button"
            className={index % 3 === 0 ? "rail-mark strong" : "rail-mark"}
            onClick={() => onSelectFigure(index)}
          >
            <b>{truncate(figure.label, 18)}</b>
            <span>{numberFormat(figure.records.length)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function FigureCardOverlay({
  figures,
  figure,
  figureIndex,
  onClose,
  onNavigate,
}: {
  figures: FigureDensityItem[];
  figure: FigureDensityItem;
  figureIndex: number;
  onClose: () => void;
  onNavigate: (direction: -1 | 1) => void;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const titleId = `figure-card-title-${slugForId(figure.label)}`;
  const statRows = [
    ["Total records", numberFormat(figure.records.length)],
    ["Mapped records", numberFormat(figure.mappedCount)],
    ["First seen", figure.earliestYear ? String(figure.earliestYear) : "undated"],
    ["Date span", figure.dateSpan],
    ["Common region", figure.topRegion],
    ["Top source", figure.topSourceFamily],
    ["Narrative family", figure.topNarrativeFamily],
  ];

  useEffect(() => {
    closeButtonRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      } else if (event.key === "ArrowLeft") {
        onNavigate(-1);
      } else if (event.key === "ArrowRight") {
        onNavigate(1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, onNavigate]);

  return (
    <div className="record-overlay figure-overlay" role="presentation" onClick={onClose}>
      <div className="figure-card-shell" onClick={(event) => event.stopPropagation()}>
        <button className="record-card-nav record-card-nav-prev figure-card-nav" type="button" onClick={(event) => { event.stopPropagation(); onNavigate(-1); }} aria-label="Previous figure">
          ‹
        </button>
        <button className="record-card-nav record-card-nav-next figure-card-nav" type="button" onClick={(event) => { event.stopPropagation(); onNavigate(1); }} aria-label="Next figure">
          ›
        </button>
        <article className="figure-profile-card" role="dialog" aria-modal="true" aria-labelledby={titleId}>
          <section className="figure-profile-left">
            <div className="figure-profile-kicker">
              <span>FIGURE PROFILE</span>
              <b>
                {numberFormat(figureIndex + 1)} / {numberFormat(figures.length)}
              </b>
            </div>
            <p>{figure.profile.shortDescription || figure.note}</p>
            {figure.profile.notes ? <p>{figure.profile.notes}</p> : null}
            <p className="figure-profile-note">
              Archive context: this card combines a static public-reference profile with computed corpus statistics. Counts describe public source records, not real-world frequency.
            </p>
            <a className="figure-reference-link" href={figure.profile.externalUrl} target="_blank" rel="noreferrer">
              {figure.profile.referenceLabel?.toUpperCase().includes("WIKIPEDIA") ? "OPEN ENCYCLOPAEDIA" : "OPEN REFERENCE"}
            </a>
          </section>
          <section className="figure-profile-right">
            <div className="figure-profile-topline">
              <span>ARCHIVE FIGURE</span>
              <button ref={closeButtonRef} type="button" onClick={onClose} aria-label="Close figure card">
                CLOSE
              </button>
            </div>
            <h2 id={titleId}>{figure.profile.label || figure.label}</h2>
            <div className="figure-profile-alias">
              {figure.profile.aliases?.length ? `aliases: ${figure.profile.aliases.slice(0, 5).join(", ")}` : "public-text category"}
            </div>
            <dl className="figure-profile-stats">
              {statRows.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <div className="figure-profile-reference">
              <span>REFERENCE</span>
              <b>{figure.profile.referenceLabel}</b>
            </div>
          </section>
        </article>
      </div>
    </div>
  );
}

function buildMappedCountByDateBand(mapFlags: readonly MapFlagRenderItem[]) {
  return mapFlags.reduce<Record<string, number>>((acc, flag) => {
    const band = flag.record.date_band;
    acc[band] = (acc[band] ?? 0) + 1;
    return acc;
  }, {});
}

function buildAnnualDensitySeries(records: readonly RecordItem[], mapFlags: readonly MapFlagRenderItem[]): AnnualDensityPoint[] {
  const totals = new Map<number, { total: number; mapped: number }>();
  for (const record of records) {
    if (typeof record.year !== "number" || !Number.isFinite(record.year)) {
      continue;
    }
    const row = totals.get(record.year) ?? { total: 0, mapped: 0 };
    row.total += 1;
    totals.set(record.year, row);
  }
  for (const flag of mapFlags) {
    const year = flag.record.year;
    if (typeof year !== "number" || !Number.isFinite(year)) {
      continue;
    }
    const row = totals.get(year) ?? { total: 0, mapped: 0 };
    row.mapped += 1;
    totals.set(year, row);
  }
  return [...totals.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([year, value]) => ({ year, total: value.total, mapped: value.mapped }));
}

function buildPeriodBoxPlotStats(
  dateBands: readonly DateBand[],
  records: readonly RecordItem[],
  mapFlags: readonly MapFlagRenderItem[],
): PeriodBoxPlotStat[] {
  const mappedByBand = buildMappedCountByDateBand(mapFlags);
  return dateBands.map((band) => {
    const byYear = new Map<number, number>();
    for (const record of records) {
      if (record.date_band !== band.id || typeof record.year !== "number" || !Number.isFinite(record.year)) {
        continue;
      }
      byYear.set(record.year, (byYear.get(record.year) ?? 0) + 1);
    }
    const values = [...byYear.values()].sort((a, b) => a - b);
    return {
      band,
      min: values[0] ?? 0,
      q1: quantile(values, 0.25),
      median: quantile(values, 0.5),
      q3: quantile(values, 0.75),
      max: values[values.length - 1] ?? 0,
      total: band.record_count,
      mapped: mappedByBand[band.id] ?? 0,
    };
  });
}

function buildFigureDensityItems(records: readonly RecordItem[], mapFlags: readonly MapFlagRenderItem[]): FigureDensityItem[] {
  const mappedIds = new Set(mapFlags.map((flag) => flag.record_id));
  const grouped = new Map<string, { profile: FigureProfile; records: RecordItem[] }>();
  for (const record of records) {
    const rawLabel = record.canonical_figure_guess || record.canonical_figure || "uncoded";
    const profile = figureProfileFor(rawLabel);
    const row = grouped.get(profile.slug) ?? { profile, records: [] };
    row.records.push(record);
    grouped.set(profile.slug, row);
  }
  return [...grouped.entries()]
    .map(([slug, group]) => {
      const { profile } = group;
      const figureRecords = group.records;
      const sortedRecords = [...figureRecords].sort(compareRecordsByDate);
      const years = sortedRecords
        .map((record) => record.year)
        .filter((year): year is number => typeof year === "number" && Number.isFinite(year));
      const topRegion = entriesDescending(
        sortedRecords.reduce<Record<string, number>>((acc, record) => {
          const region = record.state_territory ? STATE_NAMES[record.state_territory] ?? record.state_territory : "Unspecified";
          acc[region] = (acc[region] ?? 0) + 1;
          return acc;
        }, {}),
        1,
      )[0]?.[0] ?? "Unspecified";
      const topSourceFamily = entriesDescending(
        sortedRecords.reduce<Record<string, number>>((acc, record) => {
          const family = sourceFamilyFor(record.source_type).label;
          acc[family] = (acc[family] ?? 0) + 1;
          return acc;
        }, {}),
        1,
      )[0]?.[0] ?? "Public sources";
      const topNarrativeFamily = entriesDescending(
        sortedRecords.reduce<Record<string, number>>((acc, record) => {
          const narrative = narrativeGroupLabel(record);
          acc[narrative] = (acc[narrative] ?? 0) + 1;
          return acc;
        }, {}),
        1,
      )[0]?.[0] ?? "Other typed context";
      const earliestYear = years.length ? Math.min(...years) : null;
      const latestYear = years.length ? Math.max(...years) : null;
      return {
        slug,
        label: profile.label,
        profile,
        records: sortedRecords,
        mappedCount: sortedRecords.filter((record) => mappedIds.has(record.record_id)).length,
        dateSpan: earliestYear && latestYear ? `${earliestYear}-${latestYear}` : "undated only",
        earliestYear,
        latestYear,
        topSourceFamily,
        topRegion,
        topNarrativeFamily,
        note: profile.shortDescription,
      };
    })
    .sort((a, b) => b.records.length - a.records.length || a.label.localeCompare(b.label));
}

function buildSourceComposition(records: readonly RecordItem[], mapFlags: readonly MapFlagRenderItem[]): DensityChartDatum[] {
  const mappedIds = new Set(mapFlags.map((flag) => flag.record_id));
  const groups = new Map<string, { label: string; total: number; mapped: number }>();
  for (const record of records) {
    const family = sourceFamilyFor(record.source_type);
    const row = groups.get(family.id) ?? { label: family.label, total: 0, mapped: 0 };
    row.total += 1;
    if (mappedIds.has(record.record_id)) {
      row.mapped += 1;
    }
    groups.set(family.id, row);
  }
  return [...groups.entries()]
    .map(([key, row]) => ({ key, label: row.label, value: row.total, secondary: row.mapped }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
    .slice(0, 8);
}

function buildRegionConcentration(records: readonly RecordItem[], mapFlags: readonly MapFlagRenderItem[]): DensityChartDatum[] {
  const totals = new Map<string, { total: number; mapped: number }>();
  for (const record of records) {
    const code = record.state_territory || "Unspecified";
    const row = totals.get(code) ?? { total: 0, mapped: 0 };
    row.total += 1;
    totals.set(code, row);
  }
  for (const flag of mapFlags) {
    const code = flag.state_territory || flag.record.state_territory || "Unspecified";
    const row = totals.get(code) ?? { total: 0, mapped: 0 };
    row.mapped += 1;
    totals.set(code, row);
  }
  return [...totals.entries()]
    .map(([key, row]) => ({ key, label: STATE_NAMES[key] ?? key, value: row.total, secondary: row.mapped }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
}

function buildFigurePeriodMatrix(figures: readonly FigureDensityItem[], periods: readonly DateBand[]): DensityCrossRow[] {
  return figures.slice(0, 7).map((figure) => {
    const periodCounts = figure.records.reduce<Record<string, number>>((acc, record) => {
      acc[record.date_band] = (acc[record.date_band] ?? 0) + 1;
      return acc;
    }, {});
    return {
      figure: figure.label,
      total: figure.records.length,
      values: periods.map((period) => ({
        bandId: period.id,
        bandLabel: period.label,
        value: periodCounts[period.id] ?? 0,
      })),
    };
  });
}

function quantile(values: readonly number[], q: number) {
  if (!values.length) {
    return 0;
  }
  const pos = (values.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  const next = values[base + 1] ?? values[base];
  return values[base] + rest * (next - values[base]);
}

function buildLinearTicks(min: number, max: number, count: number) {
  if (count <= 1 || min === max) {
    return [min, max];
  }
  return Array.from({ length: count }, (_, index) => min + ((max - min) / (count - 1)) * index);
}

function slugForId(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "figure";
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
  const title = side === "left" ? "relation network" : "source field";
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
  "left-expanded": { left: "100%", right: "0%" },
  "right-expanded": { left: "0%", right: "100%" },
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
      .add(leftPanel, { flexBasis: target.left, duration: layout === "balanced" ? 680 : 840 }, 0)
      .add(rightPanel, { flexBasis: target.right, duration: layout === "balanced" ? 680 : 840 }, 0);
    addIfTargets(timeline, root.querySelectorAll(".dashboard-panel, .dashboard-track-network, .dashboard-console"), {
      opacity: [0.72, 1],
      translateY: [10, 0],
      duration: 760,
    }, 0);
    addIfTargets(timeline, root.querySelectorAll(".dashboard-draw-path, .console-polyline polyline"), { strokeDashoffset: 0, duration: 1180, ease: "linear", delay: stagger(28) }, 180);
    addIfTargets(timeline, root.querySelectorAll(".relation-network-node, .relation-node-count, .dashboard-axis-label, .network-slot-label, .track-row small, .console-effect-grid span, .source-wheel-list span"), {
      opacity: [0, 1],
      translateY: [4, 0],
      duration: 620,
      delay: stagger(28),
    }, 260);
    addIfTargets(timeline, root.querySelectorAll(".dashboard-track-row, .track-row"), {
      opacity: [0, 1],
      translateY: [12, 0],
      duration: 720,
      delay: stagger(34),
    }, layout === "left-expanded" ? 420 : 360);
    addIfTargets(timeline, root.querySelectorAll(".source-period-segment, .source-ribbon-segment"), {
      opacity: [0, 1],
      scaleY: [0.08, 1],
      duration: 1040,
      ease: "linear",
      delay: stagger(18),
    }, 360);
    addIfTargets(timeline, root.querySelectorAll(".source-donut, .source-donut-legend span, .source-donut-mapped-bars span, .source-insight-card"), {
      opacity: [0, 1],
      translateY: [10, 0],
      scale: [0.96, 1],
      duration: 920,
      delay: stagger(42),
    }, 520);
    addIfTargets(timeline, root.querySelectorAll(".source-family-row, .source-rank-row, .source-profile-cell"), {
      opacity: [0, 1],
      translateX: [14, 0],
      duration: 840,
      delay: stagger(28),
    }, 620);
    addIfTargets(timeline, root.querySelectorAll(".dashboard-highlight-point"), {
      filter: [
        "drop-shadow(0 0 0 rgba(159, 227, 107, 0))",
        "drop-shadow(0 0 10px rgba(159, 227, 107, .58))",
        "drop-shadow(0 0 2px rgba(159, 227, 107, .2))",
      ],
      duration: 700,
      delay: stagger(90),
    }, 880);

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

function useDensityMotion(rootRef: RefObject<HTMLDivElement | null>) {
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
      resetDensityMotion(root);
      return;
    }

    const timeline = createTimeline({
      defaults: {
        ease: "outCubic",
        composition: "replace",
      },
    });

    addIfTargets(timeline, root.querySelectorAll(".density-band"), {
      opacity: [0, 1],
      translateY: [12, 0],
      duration: 360,
      delay: stagger(42),
    }, 0);
    addIfTargets(timeline, root.querySelectorAll(".density-metric, .density-figure-rail"), {
      opacity: [0, 1],
      translateY: [10, 0],
      duration: 320,
      delay: stagger(70),
    }, 220);

    timelineRef.current = timeline;

    return () => {
      timeline.cancel();
    };
  }, [reducedMotion, rootRef]);

  useEffect(() => {
    return () => {
      timelineRef.current?.cancel();
      timelineRef.current = null;
    };
  }, []);
}

function useDensityPanelMotion(rootRef: RefObject<HTMLElement | null>, mode: DensityChartMode) {
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
      resetDensityMotion(root);
      return;
    }

    prepareDensityDrawPaths(root);
    root.querySelectorAll<HTMLElement | SVGElement>(".density-bar-fill, .density-box").forEach((element) => {
      element.style.transformOrigin = "left center";
      element.style.setProperty("transform-box", "fill-box");
    });

    const timeline = createTimeline({
      defaults: {
        ease: "outCubic",
        composition: "replace",
      },
    });

    addIfTargets(timeline, root.querySelectorAll(".density-chart-card"), {
      opacity: [0, 1],
      translateY: [8, 0],
      duration: 240,
    }, 0);
    addIfTargets(timeline, root.querySelectorAll(".density-chart-path"), {
      strokeDashoffset: 0,
      duration: 720,
      ease: "linear",
      delay: stagger(90),
    }, 80);
    addIfTargets(timeline, root.querySelectorAll(".density-bar-fill, .density-box"), {
      opacity: [0.72, 1],
      scaleX: [0, 1],
      duration: 360,
      ease: "linear",
      delay: stagger(16),
    }, 120);

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

function prepareDensityDrawPaths(root: HTMLElement) {
  root.querySelectorAll<SVGGeometryElement>(".density-chart-path").forEach((path) => {
    const length = Math.max(1, path.getTotalLength());
    path.style.strokeDasharray = String(length);
    path.style.strokeDashoffset = String(length);
  });
}

function resetDensityMotion(root: HTMLElement) {
  root.querySelectorAll<HTMLElement | SVGElement>(".density-band, .density-metric, .density-figure-rail, .density-chart-card, .density-bar-fill, .density-box").forEach((element) => {
    element.style.opacity = "";
    element.style.transform = "";
    element.style.transformOrigin = "";
    element.style.removeProperty("transform-box");
  });
  root.querySelectorAll<SVGGeometryElement>(".density-chart-path").forEach((path) => {
    path.style.strokeDasharray = "";
    path.style.strokeDashoffset = "";
  });
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
      source: expanded ? 108 : 92,
      period: expanded ? 274 : 258,
      narrative: expanded ? 486 : 466,
      place: expanded ? 684 : 650,
    };
    const laneY = (index: number, total: number) => {
      const min = expanded ? 96 : 84;
      const max = expanded ? 482 : 386;
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
  const graphViewBox = expanded ? "0 0 760 560" : "0 0 760 520";
  const graphField = expanded
    ? { x: 26, y: 64, width: 708, height: 456, y2: 520, legendY: 540 }
    : { x: 42, y: 58, width: 676, height: 396, y2: 444, legendY: 474 };
  const nodeWidth = expanded ? 164 : 146;
  const nodeHeight = expanded ? 38 : 32;
  const nodeLabelLimit = expanded ? 28 : 19;
  const setHoverRelation = (key: string | null) => {
    if (!lockedRelationKey) {
      setHoverRelationKey(key);
    }
  };

  return (
    <section
      className={`dashboard-track-network dashboard-panel dash-hover-zone${expanded ? " is-expanded" : ""}${contracted ? " is-contracted" : ""}`}
      data-dashboard-panel="left"
      aria-label="Record network and track list"
    >
      <DashboardExpandButton side="left" expanded={expanded} onToggle={onToggle} />
      <header className="dashboard-panel-title dashboard-panel-title-left">
        <span>RELATION NETWORK</span>
        <p>Source family to period to narrative type to place. Links show corpus routing, not causal relation.</p>
      </header>
      <svg className="network-svg" viewBox={graphViewBox} role="img" aria-label="Archive record relation network">
        <rect className="network-wave-box network-field-box" x={graphField.x} y={graphField.y} width={graphField.width} height={graphField.height} />
        {(["source", "period", "narrative", "place"] as RelationLane[]).map((lane) => {
          const node = graph.nodes.find((item) => item.lane === lane);
          return (
            <g className={`relation-lane relation-lane-${lane}`} key={lane}>
              <line x1={node?.x ?? 0} x2={node?.x ?? 0} y1={graphField.y + 4} y2={graphField.y2} />
              <text x={(node?.x ?? 0) - (expanded ? 64 : 52)} y={graphField.y - 12}>{lane.toUpperCase()}</text>
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
              className={`relation-edge relation-network-edge relation-edge-${edge.kind} ${sourceGraphClass(edge.sourceLabel ?? "")}${isActive ? " is-active" : isRelated ? " is-related" : ""} dashboard-draw-path`}
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
            <title>{`${node.label}: ${numberFormat(node.count)} records`}</title>
            <rect className="relation-node-hitbox" x={node.x - nodeWidth / 2 - 10} y={node.y - nodeHeight / 2 - 6} width={nodeWidth + 20} height={nodeHeight + 12} />
            <circle className="relation-node-anchor" cx={node.x - nodeWidth / 2 - 7} cy={node.y} r={expanded ? 4.6 : 3.8} />
            <rect className="relation-node-box" x={node.x - nodeWidth / 2} y={node.y - nodeHeight / 2} width={nodeWidth} height={nodeHeight} />
            <text className="relation-node-label relation-network-node" x={node.x - nodeWidth / 2 + 10} y={node.y - 3}>
              {truncate(node.label, nodeLabelLimit)}
            </text>
            <text className="relation-node-count" x={node.x - nodeWidth / 2 + 10} y={node.y + 12}>
              {numberFormat(node.count)}
            </text>
          </g>
        ))}
        <g className="relation-style-legend">
          <text x="54" y={graphField.legendY}>SOURCE STYLE</text>
          <line className="source-repository" x1="154" y1={graphField.legendY - 3} x2="190" y2={graphField.legendY - 3} />
          <text x="196" y={graphField.legendY}>repository</text>
          <line className="source-public-domain" x1="294" y1={graphField.legendY - 3} x2="330" y2={graphField.legendY - 3} />
          <text x="336" y={graphField.legendY}>public-domain</text>
          <line className="source-modern-web" x1="468" y1={graphField.legendY - 3} x2="504" y2={graphField.legendY - 3} />
          <text x="510" y={graphField.legendY}>modern web</text>
          <line className="source-academic" x1="616" y1={graphField.legendY - 3} x2="652" y2={graphField.legendY - 3} />
          <text x="658" y={graphField.legendY}>academic</text>
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
                className={`track-row dashboard-track-row${activeTrackIndex === index ? " is-active" : ""}`}
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
      className={`dashboard-console dashboard-panel dashboard-right-scroll dash-hover-zone${expanded ? " is-expanded" : ""}${contracted ? " is-contracted" : ""}`}
      data-dashboard-panel="right"
      aria-label="Public corpus control console"
    >
      <DashboardExpandButton side="right" expanded={expanded} onToggle={onToggle} />
      <header className="console-header">
        <div>
          <span>PUBLIC FIELD:</span>
          <b>{mode === "records" ? "PUBLIC RECORD ROUTES" : mode === "locations" ? "MAPPED COVERAGE" : "SOURCE FIELD"}</b>
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
        <RecordTimelineChart points={aggregate.timeline} compact />
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
        <RecordTimelineChart points={aggregate.timeline} scopeLabel={scopeLabel} />
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
        <div className="source-preview-stack">
          <SourceDonut families={aggregate.sourceFamilies} compact />
          <SourceInsightCards families={aggregate.sourceFamilies} totalRecords={aggregate.totalRecords} compact />
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-field-view source-field-view">
      <SourceInsightCards families={aggregate.sourceFamilies} totalRecords={aggregate.totalRecords} />
      <SourcePeriodRibbon families={aggregate.sourceFamilies} bands={bands} scopeLabel={scopeLabel} />
      <div className="dashboard-field-row source-bottom-row">
        <SourceDonut families={aggregate.sourceFamilies} />
      </div>
      <RankedSourceBars families={aggregate.sourceFamilies} bands={bands} />
    </div>
  );
}

function SourceInsightCards({
  families,
  totalRecords,
  compact = false,
}: {
  families: SourceFamilyAggregate[];
  totalRecords: number;
  compact?: boolean;
}) {
  const activeFamilies = families.filter((family) => family.count > 0);
  const dominant = activeFamilies[0];
  const bestMapped = [...activeFamilies].sort((a, b) => mappedShare(b) - mappedShare(a))[0];
  const widestCoverage = [...activeFamilies].sort((a, b) => b.periodCoverage - a.periodCoverage || b.narrativeSpread - a.narrativeSpread)[0];
  const cards = [
    dominant
      ? {
          label: "DOMINANT FAMILY",
          value: dominant.label,
          note: `${numberFormat(dominant.count)} records / ${formatPercent(dominant.count, totalRecords)}`,
        }
      : null,
    bestMapped
      ? {
          label: "MAPPED SUBSET",
          value: `${mappedShare(bestMapped)}% mapped`,
          note: `${bestMapped.label}; ${numberFormat(bestMapped.mappedCount)} of ${numberFormat(bestMapped.count)} records`,
        }
      : null,
    widestCoverage
      ? {
          label: "PERIOD COVERAGE",
          value: `${widestCoverage.periodCoverage}/6 periods`,
          note: `${widestCoverage.label}; ${widestCoverage.narrativeSpread} narrative groups`,
        }
      : null,
  ].filter((card): card is { label: string; value: string; note: string } => Boolean(card));

  return (
    <div className={`source-insight-cards${compact ? " compact" : ""}`}>
      {cards.slice(0, compact ? 2 : 3).map((card) => (
        <span className="source-insight-card" data-animate="source-insight" key={card.label}>
          <b>{card.label}</b>
          <strong>{card.value}</strong>
          <small>{card.note}</small>
        </span>
      ))}
    </div>
  );
}

function RecordTimelineChart({
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
    <section className="dashboard-chart-module record-timeline-module">
      {!compact ? (
        <header className="module-heading">
          <span>RECORD TIMELINE</span>
          <small>Archive records by period, not the real-world frequency of a phenomenon.</small>
        </header>
      ) : null}
      <svg className="record-timeline-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Record timeline for ${scopeLabel}`}>
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
            className="record-timeline-bar"
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
            <rect className="record-timeline-bar" x={width - 184} y="14" width="16" height="7" />
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
  const [tooltip, setTooltip] = useState<DashboardTooltipState>(null);

  return (
    <section className="dashboard-chart-module source-ribbon-module" onPointerLeave={() => setTooltip(null)}>
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
                const tooltipText = sourcePeriodTooltip(family, band, value, total);
                yCursor -= segmentHeight;
                return (
                  <rect
                    key={`${family.id}-${band.id}`}
                    className="source-ribbon-segment source-period-segment"
                    data-animate="source-ribbon"
                    tabIndex={0}
                    role="img"
                    aria-label={tooltipText}
                    x={left + bandIndex * colWidth + 4}
                    y={yCursor}
                    width={Math.max(4, colWidth - 8)}
                    height={Math.max(value > 0 ? 1.5 : 0, segmentHeight)}
                    style={{ "--source-color": family.fillColor, "--source-stroke": family.strokeColor } as CSSProperties}
                    onPointerEnter={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                    onPointerMove={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                    onFocus={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                    onBlur={() => setTooltip(null)}
                  >
                    <title>{tooltipText}</title>
                  </rect>
                );
              })}
              <text className="console-axis-label dashboard-axis-label" x={left + bandIndex * colWidth + colWidth / 2} y={height - 8}>{bandIndex + 1}</text>
            </g>
          );
        })}
        {!compact ? (
          <>
            <text className="dashboard-svg-micro dashboard-axis-label" x="8" y={top + 4}>100%</text>
            <text className="dashboard-svg-micro dashboard-axis-label" x="12" y={top + plotHeight}>0</text>
          </>
        ) : null}
      </svg>
      <DashboardTooltip tooltip={tooltip} />
    </section>
  );
}

function SourceDonut({ families, compact = false }: { families: SourceFamilyAggregate[]; compact?: boolean }) {
  const total = families.reduce((sum, family) => sum + family.count, 0) || 1;
  const visibleFamilies = families.filter((family) => family.count > 0);
  const gradient = sourceFamilyConicGradient(visibleFamilies);
  const [tooltip, setTooltip] = useState<DashboardTooltipState>(null);

  return (
    <section className={`dashboard-chart-module source-donut-module${compact ? " compact" : ""}`} data-animate="source-donut" onPointerLeave={() => setTooltip(null)}>
      {!compact ? (
        <header className="module-heading">
          <span>LARGE SOURCE DONUT</span>
          <small>Composition plus mapped coverage; counts remain raw public records.</small>
        </header>
      ) : null}
      <div className="source-donut-layout">
        <div className="source-donut" style={{ "--source-wheel": gradient } as CSSProperties}>
          <i />
        </div>
        {!compact ? (
          <div className="source-donut-companion">
            <div className="source-donut-legend">
              {visibleFamilies.map((family) => {
                const tooltipText = sourceFamilyTooltip(family, total);
                return (
                  <span
                    key={family.id}
                    data-source-family={family.id}
                    tabIndex={0}
                    title={tooltipText}
                    onPointerEnter={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                    onPointerMove={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                    onFocus={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                    onBlur={() => setTooltip(null)}
                  >
                    <b className="source-donut-slice" style={{ "--source-color": family.fillColor, "--source-stroke": family.strokeColor } as CSSProperties} />
                    <i>{family.label}</i>
                    <em>{numberFormat(family.count)} · {formatPercent(family.count, total)}</em>
                  </span>
                );
              })}
            </div>
            <SourceMappedShareBars families={visibleFamilies} />
          </div>
        ) : null}
      </div>
      <DashboardTooltip tooltip={tooltip} />
    </section>
  );
}

function SourceMappedShareBars({ families }: { families: SourceFamilyAggregate[] }) {
  return (
    <div className="source-donut-mapped-bars" data-animate="source-companion">
      <b>Mapped-share companion</b>
      <small>Bars show mapped records inside each source family, not total family size.</small>
      {families.map((family) => (
        <span key={family.id}>
          <i>{family.label}</i>
          <em style={{ "--source-meter": `${Math.max(3, mappedShare(family))}%`, "--source-color": family.fillColor, "--source-stroke": family.strokeColor } as CSSProperties} />
          <strong>{mappedShare(family)}% mapped · {family.periodCoverage}/6 periods</strong>
        </span>
      ))}
    </div>
  );
}

function RankedSourceBars({ families, bands }: { families: SourceFamilyAggregate[]; bands: readonly DateBand[] }) {
  const rows = families.filter((family) => family.count > 0);
  const total = rows.reduce((sum, family) => sum + family.count, 0) || 1;
  const max = Math.max(...rows.map((family) => family.count), 1);
  const [tooltip, setTooltip] = useState<DashboardTooltipState>(null);

  return (
    <section className="dashboard-chart-module source-ranked-module" onPointerLeave={() => setTooltip(null)}>
      <header className="module-heading">
        <span>RANKED SOURCE FAMILIES</span>
        <small>Six-period profile: darker/longer cells indicate where this source family contributes records.</small>
      </header>
      <div className="ranked-source-bars">
        <div className="source-rank-header" aria-hidden="true">
          <span>FAMILY</span>
          <span>RECORDS / SHARE</span>
          <span>TOTAL</span>
          <span>SIX-PERIOD PROFILE</span>
          <span>INSIGHT</span>
        </div>
        {rows.map((family) => {
          const profileMax = Math.max(...bands.map((band) => family.byBand[band.id] ?? 0), 1);
          return (
            <div className="source-rank-row source-family-row" data-animate="source-bar" data-source-family={family.id} key={family.id}>
              <span>{family.label}</span>
              <b>{numberFormat(family.count)} · {formatPercent(family.count, total)}</b>
              <i style={{ "--source-meter": `${Math.max(4, (family.count / max) * 100)}%`, "--source-color": family.fillColor, "--source-stroke": family.strokeColor } as CSSProperties} />
              <em>
                {bands.map((band) => {
                  const value = family.byBand[band.id] ?? 0;
                  const tooltipText = sourcePeriodTooltip(family, band, value, family.count || 1, "family");
                  return (
                    <small
                      key={`${family.id}-${band.id}`}
                      className="source-profile-cell"
                      tabIndex={0}
                      style={{ "--spark-height": `${value > 0 ? Math.max(12, (value / profileMax) * 100) : 0}%`, "--source-color": family.fillColor, "--source-stroke": family.strokeColor } as CSSProperties}
                      title={tooltipText}
                      aria-label={tooltipText}
                      onPointerEnter={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                      onPointerMove={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                      onFocus={(event) => showDashboardTooltip(event, tooltipText, setTooltip)}
                      onBlur={() => setTooltip(null)}
                    />
                  );
                })}
              </em>
              <small className="source-rank-insight">{sourceFamilyInsight(family)}</small>
            </div>
          );
        })}
      </div>
      <DashboardTooltip tooltip={tooltip} />
    </section>
  );
}

type DashboardTooltipState = {
  text: string;
  x: number;
  y: number;
} | null;

function showDashboardTooltip(
  event: { currentTarget: Element; clientX?: number; clientY?: number },
  text: string,
  setTooltip: (tooltip: DashboardTooltipState) => void,
) {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = typeof event.clientX === "number" ? event.clientX : rect.left + rect.width / 2;
  const y = typeof event.clientY === "number" ? event.clientY : rect.top;
  setTooltip({ text, x, y });
}

function DashboardTooltip({ tooltip }: { tooltip: DashboardTooltipState }) {
  if (!tooltip) {
    return null;
  }
  return (
    <span className="dashboard-tooltip" style={{ "--tooltip-x": `${tooltip.x}px`, "--tooltip-y": `${tooltip.y}px` } as CSSProperties}>
      {tooltip.text}
    </span>
  );
}

function sourcePeriodTooltip(
  family: SourceFamilyAggregate,
  band: DateBand,
  value: number,
  total: number,
  scope: "period" | "family" = "period",
) {
  const share = formatPercent(value, total);
  return `${family.label}\n${band.label}: ${numberFormat(value)} records\n${share} of this ${scope}`;
}

function sourceFamilyTooltip(family: SourceFamilyAggregate, total: number) {
  const span = family.yearStart && family.yearEnd ? `${family.yearStart}-${family.yearEnd}` : "mixed dates";
  return `${family.label}\n${numberFormat(family.count)} records / ${formatPercent(family.count, total)}\n${mappedShare(family)}% mapped; ${family.periodCoverage}/6 periods\n${family.narrativeSpread} narrative groups; ${family.jurisdictionSpread} jurisdictions; ${span}`;
}

function sourceFamilyInsight(family: SourceFamilyAggregate) {
  const parts = [
    family.dominantBandId ? `dominant ${family.dominantBandLabel} (${family.dominantBandShare}%)` : null,
    `${family.periodCoverage}/6 periods`,
    `${mappedShare(family)}% mapped`,
    `${family.narrativeSpread} narrative groups`,
    family.jurisdictionSpread ? `${family.jurisdictionSpread} jurisdictions` : null,
  ].filter(Boolean);
  return parts.join(" / ");
}

function mappedShare(family: SourceFamilyAggregate) {
  return family.count ? Math.round((family.mappedCount / family.count) * 100) : 0;
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
      translateY: [12, 0],
      duration: 760,
    }, 0);

    if (mode === "records") {
      addIfTargets(timeline, root.querySelectorAll(".record-timeline-bar"), { opacity: [0, 1], scaleY: [0.18, 1], duration: 920, ease: "linear", delay: stagger(22) }, 180);
      addIfTargets(timeline, root.querySelectorAll(".record-timeline-chart .dashboard-draw-path"), { strokeDashoffset: 0, duration: 1180, ease: "linear", delay: stagger(44) }, 260);
      addIfTargets(timeline, root.querySelectorAll(".matrix-bubble"), { opacity: [0, 1], scale: [0.2, 1], duration: 820, delay: stagger(20) }, 380);
    } else if (mode === "locations") {
      addIfTargets(timeline, root.querySelectorAll(".state-lollipop-row"), { opacity: [0, 1], translateY: [10, 0], duration: 760, delay: stagger(26) }, 160);
      addIfTargets(timeline, root.querySelectorAll(".precision-dot.lit"), { opacity: [0, 1], scale: [0.25, 1], duration: 720, delay: stagger(16) }, 320);
      addIfTargets(timeline, root.querySelectorAll(".place-role-row i"), { opacity: [0, 1], scaleX: [0.25, 1], duration: 920, ease: "linear", delay: stagger(14) }, 420);
    } else {
      addIfTargets(timeline, root.querySelectorAll(".source-insight-card"), { opacity: [0, 1], translateY: [10, 0], duration: 760, delay: stagger(38) }, 120);
      addIfTargets(timeline, root.querySelectorAll(".source-ribbon-segment, .source-period-segment"), { opacity: [0, 1], scaleY: [0.12, 1], duration: 1080, ease: "linear", delay: stagger(18) }, 220);
      addIfTargets(timeline, root.querySelectorAll(".source-donut-module, .source-donut, .source-donut-slice, .source-donut-legend span, .source-donut-mapped-bars span"), { opacity: [0, 1], translateY: [12, 0], scale: [0.95, 1], duration: 1040, delay: stagger(36) }, 430);
      addIfTargets(timeline, root.querySelectorAll(".source-family-row, .source-rank-row"), { opacity: [0, 1], translateX: [14, 0], duration: 900, delay: stagger(30) }, 640);
      addIfTargets(timeline, root.querySelectorAll(".source-profile-cell"), { opacity: [0, 1], scaleY: [0.22, 1], duration: 860, ease: "linear", delay: stagger(16) }, 760);
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
  const mappedRecordIds = new Set(mapFlags.map((flag) => flag.record_id));
  const sourceOrgSets = new Map<SourceFamilyId, Set<string>>();
  const narrativeSets = new Map<SourceFamilyId, Set<string>>();
  const jurisdictionSets = new Map<SourceFamilyId, Set<string>>();
  const sourceFamilyMap = new Map<string, SourceFamilyAggregate>(
    SOURCE_FAMILIES.map((family) => [
      family.id,
      {
        id: family.id,
        label: family.label,
        color: family.color,
        strokeColor: family.strokeColor,
        fillColor: family.fillColor,
        softColor: family.softColor,
        count: 0,
        mappedCount: 0,
        sourceOrgCount: 0,
        periodCoverage: 0,
        dominantBandId: null,
        dominantBandLabel: "no dated period",
        dominantBandShare: 0,
        narrativeSpread: 0,
        jurisdictionSpread: 0,
        yearStart: null,
        yearEnd: null,
        byBand: Object.fromEntries(dateBands.map((band) => [band.id, 0])),
      },
    ]),
  );
  for (const family of SOURCE_FAMILIES) {
    sourceOrgSets.set(family.id, new Set());
    narrativeSets.set(family.id, new Set());
    jurisdictionSets.set(family.id, new Set());
  }

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
      if (mappedRecordIds.has(record.record_id)) {
        sourceAggregate.mappedCount += 1;
      }
      if (record.date_band in sourceAggregate.byBand) {
        sourceAggregate.byBand[record.date_band] += 1;
      }
      sourceOrgSets.get(family.id)?.add(String(record.source_id || record.source_name || "unknown source"));
      narrativeSets.get(family.id)?.add(narrative);
      if (record.state_territory) {
        jurisdictionSets.get(family.id)?.add(record.state_territory);
      }
      if (typeof record.year === "number" && Number.isFinite(record.year)) {
        sourceAggregate.yearStart = sourceAggregate.yearStart === null ? record.year : Math.min(sourceAggregate.yearStart, record.year);
        sourceAggregate.yearEnd = sourceAggregate.yearEnd === null ? record.year : Math.max(sourceAggregate.yearEnd, record.year);
      }
    }
  }

  for (const family of sourceFamilyMap.values()) {
    const bandEntries = dateBands.map((band) => ({ band, value: family.byBand[band.id] ?? 0 }));
    const dominant = [...bandEntries].sort((a, b) => b.value - a.value)[0];
    family.sourceOrgCount = sourceOrgSets.get(family.id)?.size ?? 0;
    family.narrativeSpread = narrativeSets.get(family.id)?.size ?? 0;
    family.jurisdictionSpread = jurisdictionSets.get(family.id)?.size ?? 0;
    family.periodCoverage = bandEntries.filter((entry) => entry.value > 0).length;
    family.dominantBandId = dominant && dominant.value > 0 ? dominant.band.id : null;
    family.dominantBandLabel = dominant && dominant.value > 0 ? dominant.band.label : "no dated period";
    family.dominantBandShare = dominant && family.count ? Math.round((dominant.value / family.count) * 100) : 0;
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
  const id = sourceFamilyId(sourceType);
  return SOURCE_FAMILY_BY_ID.get(id) ?? SOURCE_FAMILY_BY_ID.get("other") ?? SOURCE_FAMILIES[SOURCE_FAMILIES.length - 1];
}

function sourceFamilyConicGradient(families: SourceFamilyAggregate[]) {
  const total = families.reduce((sum, family) => sum + family.count, 0) || 1;
  let cursor = 0;
  return families
    .map((family) => {
      const start = cursor;
      cursor += (family.count / total) * 100;
      return `${family.fillColor} ${start}% ${cursor}%`;
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
    return "Record timeline";
  }
  if (mode === "locations") {
    return "Mapped place coverage";
  }
  return "Source family coverage";
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
  const rawTitle = displayRecordTitle(record);
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
  return SOURCE_PUBLIC_LABELS[sourceType] ?? displaySourceType(sourceType);
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
    <div className="mini-spark" aria-label="Year pattern">
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
      <span className="tiny-label">FIELD</span>
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

function mapSourceTone(record: RecordItem) {
  const family = sourceFamilyFor(record.source_type);
  return {
    label: family.label.toUpperCase(),
    className: family.className,
  };
}

function displayRecordTitle(record: RecordItem) {
  const title = normalizeDisplayText(record.title)
    .replace(/^[\s\p{P}\p{S}]+/u, "")
    .trim();
  const fallback = normalizeDisplayText(
    record.canonical_figure_guess
      || record.canonical_figure
      || record.source_name
      || record.publication
      || "Public record",
  );
  return title && /[\p{L}\p{N}]/u.test(title) ? title : fallback;
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
    return displayRecordExcerpt(record.snippet);
  }
  const figure = displayRecordTitle(record);
  const source = record.publication || record.source_name || "a public source";
  const date = record.date_published || (record.year ? String(record.year) : "an undated record");
  return `Public record note for ${figure}, recorded in ${source} (${date}). This card is a review surface: source voice, relevance, location, and publicness still require human checking before interpretation.`;
}

function normalizeDisplayText(value: string | null | undefined) {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

function displayRecordExcerpt(value: string) {
  const text = normalizeDisplayText(value);
  if (!text) {
    return "";
  }
  const startsAbruptly = /^[a-z,;:)]/.test(text) || /^\S{2,}[-–]\S/.test(text);
  const endsAbruptly = !/[.!?]"?$/.test(text) && text.length > 120;
  return `${startsAbruptly ? "…" : ""}${text}${endsAbruptly ? "…" : ""}`;
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
          <h2 id={titleId}>{displayRecordTitle(record)}</h2>
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
