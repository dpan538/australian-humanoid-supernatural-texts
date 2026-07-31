"use client";

import type {
  CSSProperties,
  Dispatch,
  KeyboardEvent,
  PointerEvent,
  ReactNode,
  RefObject,
  SetStateAction,
} from "react";
import Link from "next/link";
import {
  createContext,
  useCallback,
  useContext,
  useDeferredValue,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createTimeline, stagger } from "animejs";
import type { AnimationParams, Timeline } from "animejs";
import { STATE_SHAPES } from "@/lib/au-map-data";
import { figurePath } from "@/lib/archive-routing";
import { figureProfileFor, normalizeFigureLabel } from "@/lib/figure-profiles";
import type { FrontendData, MapFlagItem, RecordItem } from "@/lib/types";
import { SOURCE_FAMILY_STYLES, buildSourceRegistryData, displaySourceType, sourceFamilyId, type SourceFamilyId } from "@/lib/source-view-data";
import { runThemeTransition } from "@/lib/theme-transition";

export type MobileControlView =
  | "about"
  | "map"
  | "density"
  | "dashboard"
  | "source"
  | "figures";
type DisplayTheme = "dark" | "light";
type MobileNavName = "theme" | "about" | "source" | "density" | "map" | "figures";
const MOBILE_ARCHIVE_QUERY = "(max-width: 720px)";
const THEME_STORAGE_KEY = "aus-archive-theme";
const MOBILE_NAV_STORAGE_KEY = "aus-mobile-nav-view";
const MOBILE_NAV_ITEMS: Array<{
  view: Exclude<MobileControlView, "dashboard">;
  href: string;
  label: string;
  icon: Exclude<MobileNavName, "theme">;
}> = [
  { view: "about", href: "/about", label: "About AusFigures", icon: "about" },
  { view: "map", href: "/map", label: "map", icon: "map" },
  { view: "density", href: "/density", label: "density", icon: "density" },
  { view: "source", href: "/source", label: "source", icon: "source" },
  { view: "figures", href: "/figures", label: "figures dictionary", icon: "figures" },
];
const MOBILE_MAP_VIEWBOX = { x: 24, y: 18, width: 930, height: 682 } as const;
const MOBILE_CARD_TONES = ["mint", "coral", "yellow", "blue", "lavender", "mint"] as const;
export type MobileCardTone = (typeof MOBILE_CARD_TONES)[number];
const MOBILE_SOURCE_CLASS_BY_FAMILY: Record<SourceFamilyId, string> = {
  repository: "source-tone-archive",
  modern_web: "source-tone-web",
  public_domain: "source-tone-candidate",
  institutions: "source-tone-institutional",
  academic: "source-tone-academic",
  community: "source-tone-community",
  other: "source-tone-default",
};
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

export type MobileRouteView =
  | "about"
  | "map"
  | "density"
  | "dashboard"
  | "source"
  | "figures";

type MobileArchiveData = {
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
    flags: MobileMapFlag[];
    interpretation: string;
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

type MobileMapFlag = {
  id: string;
  recordId: number;
  state: string;
  x: number;
  y: number;
  displayX: number;
  displayY: number;
  toneClass: string;
  title: string | null;
  year: number | null;
  figure: string | null;
  sourceFamily: string;
  sourceType: string;
  narrativeType: string;
};

type MobilePeriod = {
  id: string;
  label: string;
  records: number;
  mapped: number;
  mappedShare: number;
  plannedQueries: number;
  recordShare: number;
  maxShare: number;
};

const STATE_LABEL_OVERRIDES: Partial<Record<string, [number, number]>> = {
  SA: [520, 402],
  NSW: [733, 479],
  VIC: [688, 552],
  TAS: [714, 654],
  ACT: [812, 526],
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

const MOBILE_NARRATIVE_LABELS: Record<string, string> = {
  apparition_account: "Apparition Account",
  cryptid_style_apeman: "Cryptid Style Apeman",
  ghost_legend: "Ghost Legend",
  local_legend: "Local Legend",
  retelling_or_adaptation: "Retelling / Adaptation",
  spirit_person_narrative: "Spirit Person Narrative",
  traditional_narrative: "Traditional Narrative",
  giant_or_ogre_narrative: "Giant Or Ogre Narrative",
};

function buildMobileArchiveData(data: FrontendData): MobileArchiveData {
  const sourceData = buildSourceRegistryData(data);
  const mapFlags = buildMobileMapFlags(data);
  const mappedStateCounts = mapFlags.reduce<Record<string, number>>((acc, flag) => {
    acc[flag.state] = (acc[flag.state] ?? 0) + 1;
    return acc;
  }, {});
  const datedYears = data.records
    .map((record) => record.year)
    .filter((year): year is number => typeof year === "number" && Number.isFinite(year));
  const recordCount = data.summary.record_count || data.records.length;
  const mappedRecordCount = data.summary.mapped_record_count || mapFlags.length;
  const maxPeriodRecords = Math.max(1, ...data.date_bands.map((period) => period.record_count || 0));

  return {
    schema_version: "mobile-archive/v1",
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
      stateCounts: Object.keys(STATE_NAMES).map((code) => ({
        code,
        count: mappedStateCounts[code] ?? data.summary.mapped_state_counts?.[code] ?? 0,
      })),
      flags: mapFlags,
      interpretation: "Markers are public display locations for records, not proof, habitats, or populations.",
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
    .sort((a, b) => a.year - b.year);

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
  return [...counts.entries()].sort((a, b) => a[0] - b[0]).map(([year, count]) => ({ year, count }));
}

function buildMobileMapFlags(data: FrontendData): MobileMapFlag[] {
  const recordsById = new Map(data.records.map((record) => [record.record_id, record]));
  const sourceFlags = data.map_flags?.length ? data.map_flags : createMobileFallbackMapFlags(data.records);
  const seenRecordIds = new Set<number>();
  const flags: MobileMapFlag[] = [];

  for (const flag of sourceFlags) {
    const record = recordsById.get(flag.record_id);
    if (!record || seenRecordIds.has(flag.record_id)) {
      continue;
    }
    const coordinates = mobileFlagCoordinates(flag, record);
    if (!coordinates) {
      continue;
    }
    const familyId = sourceFamilyId(record.source_type);
    const family = SOURCE_FAMILY_STYLES[familyId];
    seenRecordIds.add(flag.record_id);
    flags.push({
      id: String(flag.flag_id || `mapped:${flag.record_id}`),
      recordId: flag.record_id,
      state: flag.state_territory || record.state_territory || "AU",
      x: coordinates.x,
      y: coordinates.y,
      displayX: coordinates.x,
      displayY: coordinates.y,
      toneClass: MOBILE_SOURCE_CLASS_BY_FAMILY[familyId],
      title: flag.title ?? record.title,
      year: flag.year ?? record.year,
      figure: flag.canonical_figure ?? record.canonical_figure_guess ?? record.canonical_figure,
      sourceFamily: family.label,
      sourceType: displaySourceType(record.source_type),
      narrativeType: mobileNarrativeType(record),
    });
  }

  return prepareMobileMapFlagPresentation(flags);
}

function createMobileFallbackMapFlags(records: RecordItem[]): MapFlagItem[] {
  return records.flatMap((record, index) => {
    if (!record.has_strict_map_point || record.map_latitude == null || record.map_longitude == null) {
      return [];
    }
    const projected = projectPoint(record.map_latitude, record.map_longitude);
    return [{
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
    }];
  });
}

function mobileFlagCoordinates(flag: MapFlagItem, record: RecordItem) {
  if (Number.isFinite(flag.x) && Number.isFinite(flag.y)) {
    if (flag.x >= 110 && flag.x <= 160 && flag.y >= -45 && flag.y <= -8) {
      const projected = projectPoint(flag.y, flag.x);
      return { x: svgCoord(projected.x), y: svgCoord(projected.y) };
    }
    if (flag.x >= 0 && flag.x <= MOBILE_MAP_VIEWBOX.width && flag.y >= 0 && flag.y <= MOBILE_MAP_VIEWBOX.height) {
      return { x: svgCoord(flag.x), y: svgCoord(flag.y) };
    }
  }
  if (record.map_latitude != null && record.map_longitude != null) {
    const projected = projectPoint(record.map_latitude, record.map_longitude);
    return { x: svgCoord(projected.x), y: svgCoord(projected.y) };
  }
  return null;
}

function prepareMobileMapFlagPresentation(flags: MobileMapFlag[]) {
  const groups = new Map<string, MobileMapFlag[]>();
  for (const flag of flags) {
    const key = `${flag.x.toFixed(3)}:${flag.y.toFixed(3)}`;
    const group = groups.get(key) ?? [];
    group.push(flag);
    groups.set(key, group);
  }
  for (const group of groups.values()) {
    if (group.length < 2) {
      continue;
    }
    [...group].sort((a, b) => a.recordId - b.recordId).forEach((flag, index) => {
      const offset = mobileCollisionMicroJitter(flag.recordId, index);
      flag.displayX = svgCoord(flag.x + offset.x);
      flag.displayY = svgCoord(flag.y + offset.y);
    });
  }
  return flags.sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999) || a.recordId - b.recordId);
}

function mobileNarrativeType(record: RecordItem) {
  const key = record.ontology_code || record.genre || record.canonical_figure_guess || record.canonical_figure || "other";
  return MOBILE_NARRATIVE_LABELS[key] ?? titleize(key);
}

function mobileCollisionMicroJitter(recordId: number, collisionIndex: number) {
  if (collisionIndex === 0) {
    return { x: 0, y: 0 };
  }
  const xUnit = stableUnit(recordId + collisionIndex * 97);
  const yUnit = stableUnit(recordId * 3 + collisionIndex * 193);
  return {
    x: clamp((xUnit - 0.5) * 4.2, -2.1, 2.1),
    y: clamp((yUnit - 0.5) * 3.8, -1.9, 1.9),
  };
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
    x: clamp(x, SVG_BOUNDS.minX + 4, SVG_BOUNDS.maxX - 4),
    y: clamp(y, SVG_BOUNDS.minY + 4, SVG_BOUNDS.maxY - 4),
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

function stableUnit(seed: number) {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function svgCoord(value: number) {
  return Number(value.toFixed(3));
}

function titleize(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function MobileArchiveView({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function useMobileArchiveMode() {
  const [mode, setMode] = useState({ ready: false, isMobile: false });

  useEffect(() => {
    const mediaQuery = window.matchMedia(MOBILE_ARCHIVE_QUERY);
    const syncMode = () => setMode({ ready: true, isMobile: mediaQuery.matches });

    syncMode();
    mediaQuery.addEventListener("change", syncMode);
    return () => mediaQuery.removeEventListener("change", syncMode);
  }, []);

  return mode;
}

export function useMobileArchiveRouteGuard(view: MobileControlView) {
  void view;
  return { blockedDashboard: false };
}

export function MobileArchiveRoute({ view, data }: { view: MobileControlView; data: FrontendData }) {
  const routeView: MobileRouteView = view;
  const mobileData = useMemo(() => buildMobileArchiveData(data), [data]);
  const pageRef = useRef<HTMLElement | null>(null);
  const reducedMotion = useMobilePrefersReducedMotion();

  useMobilePageAmbientMotion(pageRef, reducedMotion);

  return (
    <main className={`terminal-shell mobile-archive-shell mobile-view-${routeView}`}>
      <h1 className="visually-hidden">{mobileRouteHeading(routeView)}</h1>
      <div className="noise-layer" aria-hidden="true" />
      <MobileTopBar view={routeView} figures={mobileData.figures} />
      <section ref={pageRef} className="mobile-archive-page" aria-label={`AusFigures ${routeView} mobile view`}>
        {routeView === "map" ? <MobileMapView data={mobileData} /> : null}
        {routeView === "density" ? <MobileDensityView data={mobileData} /> : null}
        {routeView === "dashboard" ? <MobileDashboardView data={mobileData} /> : null}
        {routeView === "source" ? <MobileSourceView data={mobileData} /> : null}
        {routeView === "about" ? <MobileAboutView data={mobileData} /> : null}
      </section>
      <MobileArchiveControls view={routeView} />
    </main>
  );
}

export function MobileTopBar({
  view,
  figures,
}: {
  view: MobileRouteView;
  figures: MobileFigureSearchEntry[];
}) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const reducedMotion = useMobilePrefersReducedMotion();
  const results = useMemo(
    () => rankMobileFigureSearch(figures, deferredQuery).slice(0, 8),
    [deferredQuery, figures],
  );

  useEffect(() => {
    if (!searchOpen) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => inputRef.current?.focus());
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        setSearchOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [searchOpen]);

  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay || !searchOpen || reducedMotion) {
      return;
    }
    const panel = overlay.querySelector(".mobile-search-panel");
    const rows = overlay.querySelectorAll(".mobile-search-result");
    const timeline = createTimeline({
      defaults: {
        ease: "outQuint",
        composition: "replace",
      },
    });
    if (panel) {
      timeline.add(panel, {
        opacity: [0, 1],
        translateY: [26, 0],
        scale: [0.975, 1],
        duration: 460,
      }, 0);
    }
    if (rows.length) {
      timeline.add(rows, {
        opacity: [0, 1],
        translateY: [18, 0],
        delay: stagger(42),
        duration: 360,
      }, 90);
    }
    return () => {
      timeline.cancel();
    };
  }, [reducedMotion, searchOpen]);

  return (
    <>
      <header className="mobile-topbar" aria-label="Mobile page controls">
        <MobileThemeControl />
        <span className="mobile-top-route" aria-hidden="true">
          {view === "figures"
            ? `FIGURES · ${figures.length}`
            : view.toUpperCase()}
        </span>
        <button
          type="button"
          className="mobile-top-action mobile-top-search"
          aria-label="Search the supernatural humanoid dictionary"
          aria-expanded={searchOpen}
          onClick={() => setSearchOpen(true)}
        >
          <MobileTopIcon name="search" />
        </button>
      </header>
      {searchOpen ? (
        <div
          ref={overlayRef}
          className="mobile-search-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Search supernatural humanoid figures"
          onPointerDown={(event) => {
            if (event.target === event.currentTarget) {
              setSearchOpen(false);
            }
          }}
        >
          <section className="mobile-search-panel">
            <header>
              <span>FIND A FIGURE</span>
              <button type="button" onClick={() => setSearchOpen(false)} aria-label="Close search">
                <MobileTopIcon name="close" />
              </button>
            </header>
            <label className="mobile-search-input">
              <MobileTopIcon name="search" />
              <input
                ref={inputRef}
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="yowie, ghost, hairy man…"
                autoComplete="off"
                spellCheck={false}
              />
              {query ? (
                <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
                  Clear
                </button>
              ) : null}
            </label>
            <div className="mobile-search-meta">
              <span>{deferredQuery ? "BEST FUZZY MATCHES" : "HIGH-FREQUENCY FIGURES"}</span>
              <b>{formatNumber(figures.length)} entries</b>
            </div>
            <div className="mobile-search-results">
              {results.map((entry, index) => (
                <Link
                  key={entry.slug}
                  className="mobile-search-result"
                  data-tone={MOBILE_CARD_TONES[index % MOBILE_CARD_TONES.length]}
                  href={figurePath(entry.slug)}
                  onClick={() => setSearchOpen(false)}
                >
                  <span className="mobile-search-rank">{String(index + 1).padStart(2, "0")}</span>
                  <span className="mobile-search-copy">
                    <b>{entry.name}</b>
                    <small>{mobileSearchSupportingText(entry)}</small>
                  </span>
                  <strong>{formatNumber(entry.recordCount)}</strong>
                  <i aria-hidden="true">↗</i>
                </Link>
              ))}
              {results.length === 0 ? (
                <p className="mobile-search-empty">No close figure or alias match was found. Try a broader term.</p>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}

function MobileTopIcon({ name }: { name: "about" | "search" | "close" }) {
  if (name === "search") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="10.5" cy="10.5" r="5.4" />
        <path d="m14.4 14.4 4.1 4.1" />
      </svg>
    );
  }
  if (name === "close") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="m6.5 6.5 11 11" />
        <path d="m17.5 6.5-11 11" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="7.2" />
      <path d="M12 10.6v5" />
      <circle cx="12" cy="7.5" r=".7" className="mobile-icon-fill" />
    </svg>
  );
}

function rankMobileFigureSearch(
  figures: MobileFigureSearchEntry[],
  query: string,
) {
  const normalisedQuery = normaliseMobileSearch(query);
  if (!normalisedQuery) {
    return figures;
  }
  return figures
    .map((entry) => ({
      entry,
      score: Math.max(
        mobileFuzzyScore(normalisedQuery, normaliseMobileSearch(entry.name)),
        ...entry.aliases.map((alias) => mobileFuzzyScore(normalisedQuery, normaliseMobileSearch(alias))),
        mobileFuzzyScore(normalisedQuery, normaliseMobileSearch(entry.description)) - 16,
      ),
    }))
    .filter((row) => row.score > 0)
    .sort((left, right) => right.score - left.score || right.entry.recordCount - left.entry.recordCount)
    .map((row) => row.entry);
}

function normaliseMobileSearch(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function mobileFuzzyScore(query: string, target: string) {
  if (!query || !target) {
    return 0;
  }
  if (target === query) {
    return 120;
  }
  if (target.startsWith(query)) {
    return 104 - Math.min(20, target.length - query.length);
  }
  const targetWords = target.split(" ");
  if (targetWords.some((word) => word.startsWith(query))) {
    return 92;
  }
  if (target.includes(query)) {
    return 82 - Math.min(24, target.indexOf(query));
  }
  if (isMobileSearchSubsequence(query, target)) {
    return 60 - Math.min(28, target.length - query.length);
  }
  const nearestWordDistance = Math.min(
    ...targetWords.map((word) => mobileLevenshtein(query, word)),
  );
  const tolerance = Math.max(1, Math.floor(query.length * 0.34));
  return nearestWordDistance <= tolerance ? 46 - nearestWordDistance * 6 : 0;
}

function isMobileSearchSubsequence(query: string, target: string) {
  let queryIndex = 0;
  for (const character of target) {
    if (character === query[queryIndex]) {
      queryIndex += 1;
      if (queryIndex === query.length) {
        return true;
      }
    }
  }
  return false;
}

function mobileLevenshtein(left: string, right: string) {
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    let diagonal = previous[0];
    previous[0] = leftIndex;
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      const above = previous[rightIndex];
      previous[rightIndex] = Math.min(
        previous[rightIndex] + 1,
        previous[rightIndex - 1] + 1,
        diagonal + (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1),
      );
      diagonal = above;
    }
  }
  return previous[right.length];
}

function mobileSearchSupportingText(entry: MobileFigureSearchEntry) {
  const span = entry.earliestYear && entry.latestYear
    ? `${entry.earliestYear}–${entry.latestYear}`
    : "undated span";
  const aliases = entry.aliases.slice(0, 2).join(", ");
  return aliases ? `${span} / ${aliases}` : `${span} / public-text figure`;
}

function useMobilePageAmbientMotion(
  rootRef: RefObject<HTMLElement | null>,
  reducedMotion: boolean,
) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root || reducedMotion) {
      return;
    }

    const redrawTargets = Array.from(
      root.querySelectorAll<SVGGeometryElement>(".mobile-map-canvas .state-shape, .mobile-map-canvas .coast-outline"),
    );
    const mapDots = Array.from(root.querySelectorAll<SVGCircleElement>(".mobile-map-canvas .mobile-map-dot"));
    const revealTargets = Array.from(root.querySelectorAll<HTMLElement>([
      ".mobile-map-heading",
      ".mobile-map-dashboard-card",
      ".density-header",
      ".mobile-density-overview-card",
      ".mobile-card-deck > .mobile-expand-card",
      ".mobile-dashboard-hero",
      ".mobile-analysis-card",
      ".source-terminal-header",
      ".mobile-source-visual-card",
      ".mobile-about-heading",
      ".about-status-panel",
      ".mobile-about-repository-link",
    ].join(",")));
    const revealTimelines = new Set<Timeline>();
    const revealTimers = new Set<number>();
    const resetRedrawTargets = () => {
      redrawTargets.forEach((target) => {
        target.style.strokeDasharray = "";
        target.style.strokeDashoffset = "";
      });
    };
    const resetMapDots = () => {
      mapDots.forEach((target) => {
        target.style.opacity = "";
        target.style.transform = "";
      });
    };

    redrawTargets.forEach((target) => {
      const length = target.getTotalLength();
      target.style.strokeDasharray = `${length}`;
      target.style.strokeDashoffset = `${length}`;
    });
    mapDots.forEach((target) => {
      target.style.opacity = "0";
      target.style.transform = "scale(0.22)";
    });
    revealTargets.forEach((target) => {
      target.style.opacity = "0";
      target.style.transform = "translateY(24px) scale(0.985)";
      target.style.transformOrigin = "50% 50%";
      target.style.willChange = "transform, opacity";
    });

    let redrawTimeline: Timeline | null = null;
    let revealObserver: IntersectionObserver | null = null;
    const revealTarget = (target: HTMLElement) => {
      if (target.dataset.mobileRevealed === "true") {
        return;
      }
      target.dataset.mobileRevealed = "true";
      revealObserver?.unobserve(target);
      const timeline = createTimeline({
        defaults: {
          ease: "outQuint",
          composition: "replace",
        },
      });
      timeline.add(target, {
        opacity: [0, 1],
        translateY: [24, 0],
        scale: [0.985, 1],
        duration: 620,
      }, 0);
      const directChildren = target.querySelectorAll(":scope > header, :scope > strong, :scope > p");
      if (directChildren.length) {
        timeline.add(directChildren, {
          opacity: [0.35, 1],
          translateY: [10, 0],
          delay: stagger(36),
          duration: 420,
        }, 80);
      }
      revealTimelines.add(timeline);
      const cleanupTimer = window.setTimeout(() => {
        target.style.opacity = "";
        target.style.transform = "";
        target.style.transformOrigin = "";
        target.style.willChange = "";
        revealTimers.delete(cleanupTimer);
      }, 680);
      revealTimers.add(cleanupTimer);
    };
    const revealFrame = window.requestAnimationFrame(() => {
      if (!("IntersectionObserver" in window)) {
        revealTargets.forEach(revealTarget);
        return;
      }
      revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            revealTarget(entry.target as HTMLElement);
          }
        });
      }, {
        threshold: 0.08,
        rootMargin: "0px 0px -6% 0px",
      });
      revealTargets.forEach((target) => revealObserver?.observe(target));
    });
    const redrawFrame = window.requestAnimationFrame(() => {
      redrawTimeline = createTimeline({
        defaults: {
          ease: "outCubic",
          duration: 780,
          composition: "replace",
        },
      });
      addMobileTimelineTargets(
        redrawTimeline,
        redrawTargets,
        { strokeDashoffset: 0, duration: 1420, ease: "linear", delay: stagger(18) },
        110,
      );
      addMobileTimelineTargets(
        redrawTimeline,
        mapDots,
        { opacity: [0, 1], scale: [0.22, 1], duration: 880, ease: "outCubic", delay: stagger(1.4) },
        280,
      );
    });

    return () => {
      window.cancelAnimationFrame(revealFrame);
      window.cancelAnimationFrame(redrawFrame);
      revealObserver?.disconnect();
      revealTimelines.forEach((timeline) => timeline.cancel());
      revealTimers.forEach((timer) => window.clearTimeout(timer));
      redrawTimeline?.cancel();
      resetRedrawTargets();
      resetMapDots();
      revealTargets.forEach((target) => {
        delete target.dataset.mobileRevealed;
        target.style.opacity = "";
        target.style.transform = "";
        target.style.transformOrigin = "";
        target.style.willChange = "";
      });
    };
  }, [reducedMotion, rootRef]);
}

function mobileRouteHeading(view: MobileRouteView) {
  if (view === "density") {
    return "AusFigures density explorer";
  }
  if (view === "source") {
    return "AusFigures source register";
  }
  if (view === "dashboard") {
    return "AusFigures research dashboard";
  }
  if (view === "about") {
    return "About AusFigures";
  }
  if (view === "figures") {
    return "AusFigures supernatural humanoid dictionary";
  }
  return "AusFigures public map";
}

function MobileMapView({ data }: { data: MobileArchiveData }) {
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const [activeSignal, setActiveSignal] = useState<0 | 1>(0);
  const titleId = useId();
  const descId = useId();
  const clipBaseId = useId().replace(/:/g, "");
  const touchStateHandled = useRef(false);
  const signalTrackRef = useRef<HTMLDivElement | null>(null);
  const signalTimelineRef = useRef<Timeline | null>(null);
  const previousSignalRef = useRef<0 | 1>(0);
  const reducedMotion = useMobilePrefersReducedMotion();
  const stateCounts = data.map.stateCounts;
  const stateCountMap = new Map(stateCounts.map((row) => [row.code, row.count]));
  const activeState = selectedState ? STATE_NAMES[selectedState] ?? selectedState : "Australia";
  const activeCount = selectedState ? stateCountMap.get(selectedState) ?? 0 : data.summary.mappedRecordCount;
  const activeMappedShare = data.summary.mappedRecordCount
    ? activeCount / data.summary.mappedRecordCount
    : 0;
  const nationalMappedCoverage = data.summary.recordCount
    ? data.summary.mappedRecordCount / data.summary.recordCount
    : 0;
  const maxStateCount = Math.max(1, ...stateCounts.map((row) => row.count));
  const leadingMapPeriod = [...data.density.periods]
    .sort((left, right) => right.records - left.records)[0];
  const toggleSelectedState = useCallback((stateCode: string) => {
    setSelectedState((current) => (current === stateCode ? null : stateCode));
  }, []);
  const handleStateClick = useCallback((stateCode: string) => {
    if (touchStateHandled.current) {
      touchStateHandled.current = false;
      return;
    }
    toggleSelectedState(stateCode);
  }, [toggleSelectedState]);
  const handleStatePointerUp = useCallback((event: PointerEvent<SVGPathElement>, stateCode: string) => {
    if (event.pointerType === "mouse") {
      return;
    }
    event.preventDefault();
    touchStateHandled.current = true;
    toggleSelectedState(stateCode);
  }, [toggleSelectedState]);
  const handleStateKeyDown = useCallback((event: KeyboardEvent<SVGPathElement>, stateCode: string) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    toggleSelectedState(stateCode);
  }, [toggleSelectedState]);
  const syncMapSignal = useCallback(() => {
    const track = signalTrackRef.current;
    if (!track || track.clientWidth <= 0) {
      return;
    }
    const nextIndex: 0 | 1 = Math.round(track.scrollLeft / track.clientWidth) <= 0 ? 0 : 1;
    setActiveSignal((current) => current === nextIndex ? current : nextIndex);
  }, []);

  useEffect(() => {
    const track = signalTrackRef.current;
    const slide = track?.querySelector<HTMLElement>(`[data-map-signal="${activeSignal}"]`);
    if (!slide || reducedMotion) {
      previousSignalRef.current = activeSignal;
      return;
    }
    const direction = activeSignal >= previousSignalRef.current ? 1 : -1;
    previousSignalRef.current = activeSignal;
    signalTimelineRef.current?.cancel();
    const timeline = createTimeline({
      defaults: {
        ease: "outQuint",
        composition: "replace",
      },
    });
    const copy = track?.parentElement?.querySelectorAll(
      ".mobile-map-signal-swipe-head > div > *, .mobile-map-swipe-cue",
    ) ?? [];
    const marks = slide.querySelectorAll(".mobile-map-region-bars i, .mobile-map-period-bars i");
    if (copy.length) {
      timeline.add(copy, {
        opacity: [0.46, 1],
        translateX: [direction * 20, 0],
        duration: 420,
        delay: stagger(34),
      }, 0);
    }
    if (marks.length) {
      timeline.add(marks, {
        opacity: [0.5, 1],
        scaleY: [0.42, 1],
        transformOrigin: "50% 100%",
        duration: 520,
        delay: stagger(28),
      }, 40);
    }
    signalTimelineRef.current = timeline;
    return () => {
      timeline.cancel();
    };
  }, [activeSignal, reducedMotion]);

  return (
    <div className="map-view mobile-map-view">
      <header className="mobile-map-heading">
        <span>PUBLIC MAP</span>
        <b>Public display locations</b>
      </header>
      <article className="mobile-map-dashboard-card">
        <div className="map-canvas mobile-map-canvas">
          <svg
            className="australia-map"
            viewBox={`${MOBILE_MAP_VIEWBOX.x} ${MOBILE_MAP_VIEWBOX.y} ${MOBILE_MAP_VIEWBOX.width} ${MOBILE_MAP_VIEWBOX.height}`}
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-labelledby={titleId}
            aria-describedby={descId}
          >
            <title id={titleId}>Public record display locations across Australia</title>
            <desc id={descId}>
              Schematic dot map clipped to the Australian state and territory shapes, summarising {formatNumber(data.summary.mappedRecordCount)} mapped public records.
            </desc>
            <defs>
              <clipPath id={`${clipBaseId}-australia`}>
                {STATE_SHAPES.map((state) => <path key={`mobile-country-clip-${state.code}`} d={state.d} />)}
              </clipPath>
              <pattern id={`${clipBaseId}-dots`} width="22" height="22" patternUnits="userSpaceOnUse">
                <circle className="mobile-map-dot" cx="4" cy="4" r="3.2" />
              </pattern>
              <pattern id={`${clipBaseId}-selected-dots`} width="22" height="22" patternUnits="userSpaceOnUse">
                <circle className="mobile-map-dot selected" cx="4" cy="4" r="4.1" />
              </pattern>
              {STATE_SHAPES.map((state) => (
                <clipPath id={`${clipBaseId}-${state.code.toLowerCase()}`} key={`mobile-state-clip-${state.code}`}>
                  <path d={state.d} />
                </clipPath>
              ))}
            </defs>
            {STATE_SHAPES.map((state) => {
              const count = stateCountMap.get(state.code) ?? 0;
              return (
                <path
                  key={state.code}
                  className={selectedState === state.code ? "state-shape selected" : "state-shape"}
                  d={state.d}
                  role="button"
                  tabIndex={0}
                  aria-label={`${STATE_NAMES[state.code] ?? state.code}, ${formatNumber(count)} mapped records`}
                  aria-pressed={selectedState === state.code}
                  onClick={() => handleStateClick(state.code)}
                  onPointerUp={(event) => handleStatePointerUp(event, state.code)}
                  onKeyDown={(event) => handleStateKeyDown(event, state.code)}
                />
              );
            })}
            <rect
              className="mobile-map-dot-field"
              x={MOBILE_MAP_VIEWBOX.x}
              y={MOBILE_MAP_VIEWBOX.y}
              width={MOBILE_MAP_VIEWBOX.width}
              height={MOBILE_MAP_VIEWBOX.height}
              fill={`url(#${clipBaseId}-dots)`}
              clipPath={`url(#${clipBaseId}-australia)`}
              aria-hidden="true"
            />
            {selectedState ? (
              <rect
                className="mobile-map-dot-field is-selected"
                x={MOBILE_MAP_VIEWBOX.x}
                y={MOBILE_MAP_VIEWBOX.y}
                width={MOBILE_MAP_VIEWBOX.width}
                height={MOBILE_MAP_VIEWBOX.height}
                fill={`url(#${clipBaseId}-selected-dots)`}
                clipPath={`url(#${clipBaseId}-${selectedState.toLowerCase()})`}
                aria-hidden="true"
              />
            ) : null}
            <g className="state-label-layer" aria-hidden="true">
              {STATE_SHAPES.map((state) => {
                const label = STATE_LABEL_OVERRIDES[state.code] ?? state.label;
                return (
                  <g key={`mobile-label-${state.code}`} className={selectedState === state.code ? "mobile-state-marker is-selected" : "mobile-state-marker"}>
                    <text
                      className={`state-label state-label-${state.code.toLowerCase()}`}
                      x={label[0]}
                      y={label[1]}
                    >
                      {state.code}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
        <section className="mobile-map-analysis" aria-label="Regional mapped-record analysis">
          <header className="mobile-map-active">
            <div>
              <span>{activeState}</span>
              <strong>{formatNumber(activeCount)}</strong>
              <small>mapped records</small>
            </div>
            <div>
              <b>{selectedState ? `${(activeMappedShare * 100).toFixed(1)}%` : `${(nationalMappedCoverage * 100).toFixed(1)}%`}</b>
              <small>{selectedState ? "of mapped layer" : "mapped of public"}</small>
            </div>
          </header>
          <div className="mobile-map-signal-carousel" data-active-signal={activeSignal}>
            <header className="mobile-map-signal-swipe-head" aria-live="polite">
              <div>
                <span>{activeSignal === 0 ? "REGION VOLUME" : "TIME DENSITY"}</span>
                <b>
                  {activeSignal === 0
                    ? `${stateCounts.length} regions`
                    : leadingMapPeriod
                      ? `${formatNumber(leadingMapPeriod.records)} · ${leadingMapPeriod.label}`
                      : "—"}
                </b>
              </div>
              <span className="mobile-map-swipe-cue" aria-hidden="true">
                <svg viewBox="0 0 32 20">
                  <path d="m8 4-5 6 5 6M24 4l5 6-5 6M4 10h24" />
                </svg>
                <small>{activeSignal + 1}/2</small>
              </span>
            </header>
            <div
              ref={signalTrackRef}
              className="mobile-map-signal-track"
              onScroll={syncMapSignal}
              data-testid="mobile-map-signal-track"
              role="region"
              aria-label="Swipe between region volume and time density charts"
              tabIndex={0}
            >
              <section
                className="mobile-map-signal-slide"
                data-map-signal="0"
                role="group"
                aria-roledescription="slide"
                aria-label="Region volume, 1 of 2"
              >
                <div className="mobile-map-region-bars" aria-label="Mapped record volume by state and territory">
                  {stateCounts.map((row) => (
                    <button
                      type="button"
                      className={selectedState === row.code ? "is-active" : ""}
                      key={row.code}
                      onClick={() => toggleSelectedState(row.code)}
                      aria-pressed={selectedState === row.code}
                      aria-label={`${STATE_NAMES[row.code] ?? row.code}, ${formatNumber(row.count)} mapped records`}
                    >
                      <span aria-hidden="true">
                        <i style={{ "--map-volume": row.count / maxStateCount } as CSSProperties} />
                      </span>
                      <b aria-hidden="true">{row.code}</b>
                    </button>
                  ))}
                </div>
              </section>
              <section
                className="mobile-map-signal-slide"
                data-map-signal="1"
                role="group"
                aria-roledescription="slide"
                aria-label="Time density, 2 of 2"
              >
                <div className="mobile-map-period-bars" aria-label="Archive density across seven research periods">
                  {data.density.periods.map((period, index) => (
                    <span key={period.id}>
                      <i style={{ "--map-period-volume": period.maxShare } as CSSProperties} />
                      <b>{index + 1}</b>
                    </span>
                  ))}
                </div>
              </section>
            </div>
            <div className="mobile-map-signal-progress" aria-hidden="true">
              <i />
            </div>
          </div>
          <p>Schematic display volumes, not incidence or one marker per record.</p>
        </section>
      </article>
    </div>
  );
}

function MobileDashboardView({ data }: { data: MobileArchiveData }) {
  const mappedShare = data.summary.recordCount
    ? data.summary.mappedRecordCount / data.summary.recordCount
    : 0;
  const leadingFamily = data.sources.rollup[0];
  const leadingPeriod = [...data.density.periods]
    .sort((left, right) => right.records - left.records)[0];
  const leadingFamilyShare = leadingFamily
    ? leadingFamily.records / Math.max(1, data.summary.recordCount)
    : 0;
  const leadingThreeFamilyShare = data.sources.rollup
    .slice(0, 3)
    .reduce((total, row) => total + row.records, 0)
    / Math.max(1, data.summary.recordCount);
  const leadingFigures = [...data.figures]
    .sort((left, right) => right.recordCount - left.recordCount)
    .slice(0, 4);
  const leadingFigure = leadingFigures[0];
  const mappedAnalysisCells = Math.round(mappedShare * 20);

  return (
    <div className="mobile-dashboard-view">
      <header className="mobile-dashboard-hero">
        <span>ARCHIVE OVERVIEW</span>
        <div>
          <h2>Public data</h2>
          <strong>{formatNumber(data.summary.recordCount)}</strong>
        </div>
        <p>
          Accepted public-text records across supernatural humanoid and adjacent figures;
          counts describe archive coverage, not incidence.
        </p>
      </header>

      <section className="mobile-dashboard-analysis-grid" aria-label="Mobile archive analysis">
        <article
          className="mobile-analysis-card is-concrete"
          aria-label={`${formatNumber(data.summary.mappedRecordCount)} public records have a mapped display location`}
        >
          <strong>{formatNumber(data.summary.mappedRecordCount)}</strong>
          <p>Mapped records</p>
          <div className="mobile-analysis-matrix" aria-hidden="true">
            {Array.from({ length: 20 }, (_, index) => (
              <i className={index < mappedAnalysisCells ? "is-filled" : ""} key={`mapped-cell-${index}`} />
            ))}
          </div>
        </article>

        <article
          className="mobile-analysis-card is-sand"
          aria-label={`${leadingPeriod?.label ?? "Largest period"} contains ${formatNumber(leadingPeriod?.records ?? 0)} public records`}
        >
          <strong>{leadingPeriod ? formatNumber(leadingPeriod.records) : "—"}</strong>
          <p>{leadingPeriod?.label ?? "No dated period"}</p>
          <div className="mobile-analysis-columns" aria-hidden="true">
            {data.density.periods.map((period) => (
              <span
                key={period.id}
                style={{
                  "--analysis-volume": period.maxShare,
                  "--analysis-mapped": period.mappedShare,
                } as CSSProperties}
              >
                <i><em /></i>
              </span>
            ))}
          </div>
        </article>

        <article
          className="mobile-analysis-card is-orange"
          aria-label={`${formatNumber(leadingFamily?.records ?? 0)} public records belong to the largest source family`}
        >
          <strong>{leadingFamily ? formatNumber(leadingFamily.records) : "—"}</strong>
          <p>{leadingFamily?.label ?? "Public sources"}</p>
          <div className="mobile-analysis-rings" aria-hidden="true">
            <svg viewBox="0 0 120 120">
              <circle className="ring-track ring-outer" cx="60" cy="60" r="44" pathLength="100" />
              <circle
                className="ring-value ring-outer"
                cx="60"
                cy="60"
                r="44"
                pathLength="100"
                strokeDasharray={`${leadingFamilyShare * 100} ${100 - (leadingFamilyShare * 100)}`}
              />
              <circle className="ring-track ring-inner" cx="60" cy="60" r="29" pathLength="100" />
              <circle
                className="ring-value ring-inner"
                cx="60"
                cy="60"
                r="29"
                pathLength="100"
                strokeDasharray={`${leadingThreeFamilyShare * 100} ${100 - (leadingThreeFamilyShare * 100)}`}
              />
            </svg>
          </div>
        </article>

        <article
          className="mobile-analysis-card is-olive"
          aria-label={`${leadingFigure?.name ?? "Leading figure"} has ${formatNumber(leadingFigure?.recordCount ?? 0)} public records`}
        >
          <strong>{leadingFigure ? formatNumber(leadingFigure.recordCount) : "—"}</strong>
          <p>{leadingFigure?.name ?? "No indexed figure"}</p>
          <div className="mobile-analysis-treemap" aria-hidden="true">
            {leadingFigures.map((figure) => {
              const relativeWeight = leadingFigure
                ? figure.recordCount / Math.max(1, leadingFigure.recordCount)
                : 0;
              return (
                <span
                  key={figure.slug}
                  style={{
                    "--analysis-height": `${Math.round(32 + (relativeWeight * 68))}%`,
                    "--analysis-weight": Math.max(0.18, relativeWeight),
                  } as CSSProperties}
                />
              );
            })}
          </div>
        </article>
      </section>
    </div>
  );
}

function MobileDensityView({ data }: { data: MobileArchiveData }) {
  const compactPeriods = data.density.periods.filter((period) => period.records < 100);
  const chartPeriods = data.density.periods.filter((period) => period.records >= 100);
  const periodRanks = new Map(
    [...data.density.periods]
      .sort((left, right) => right.records - left.records)
      .map((period, index) => [period.id, index + 1]),
  );
  const peakYear = data.density.annualSeries.reduce(
    (best, row) => (row.count > best.count ? row : best),
    data.density.annualSeries[0] ?? { year: data.summary.earliestYear, count: 0 },
  );

  return (
    <div className="density-view mobile-density-view">
      <header className="density-header">
        <div className="density-header-title">
          <span>TIME DENSITY</span>
          <strong>{formatNumber(data.summary.recordCount)}</strong>
          <p>public records by year and archive period</p>
        </div>
        <div className="density-header-stats" aria-label="Density summary">
          <span><b>{formatNumber(data.summary.mappedRecordCount)}</b><small>MAPPED</small></span>
          <span><b>{data.density.periods.length}</b><small>PERIODS</small></span>
          <span><b>{data.summary.earliestYear}–{data.summary.latestYear}</b><small>SPAN</small></span>
        </div>
        <small className="density-header-note">Archive coverage, not real-world incidence.</small>
      </header>
      <section className="mobile-density-overview-card" aria-label="Annual dated-record overview">
        <header>
          <span>ANNUAL SERIES</span>
          <strong>{formatNumber(peakYear.count)}</strong>
          <small>{peakYear.year} peak year</small>
        </header>
        <MobileAnnualSparkline series={data.density.annualSeries} />
      </section>
      <section className="mobile-density-minor-grid" aria-label="Smaller archive period volumes">
        {compactPeriods.map((period, compactIndex) => {
          const archiveIndex = data.density.periods.findIndex((candidate) => candidate.id === period.id);
          return (
            <article
              key={period.id}
              data-tone={MOBILE_CARD_TONES[compactIndex % 3]}
              aria-label={`${period.label}, ${formatNumber(period.records)} records`}
            >
              <span>PERIOD {String(archiveIndex + 1).padStart(2, "0")}</span>
              <strong>{formatNumber(period.records)}</strong>
              <p>{period.label}</p>
            </article>
          );
        })}
      </section>
      <MobileCardDeck className="density-bands">
        {chartPeriods.map((period, visualIndex) => {
          const archiveIndex = data.density.periods.findIndex((candidate) => candidate.id === period.id);
          return (
          <MobileDensityBand
            key={period.id}
            period={period}
            index={archiveIndex}
            visualIndex={visualIndex}
            rank={periodRanks.get(period.id) ?? data.density.periods.length}
            totalPeriods={data.density.periods.length}
          />
          );
        })}
      </MobileCardDeck>
    </div>
  );
}

function MobileDensityBand({
  period,
  index,
  visualIndex,
  rank,
  totalPeriods,
}: {
  period: MobilePeriod;
  index: number;
  visualIndex: number;
  rank: number;
  totalPeriods: number;
}) {
  return (
    <MobileExpandableCard
      cardId={`density-${period.id}`}
      className="density-band"
      tone={MOBILE_CARD_TONES[index % MOBILE_CARD_TONES.length]}
      eyebrow={`ARCHIVE PERIOD ${String(index + 1).padStart(2, "0")}`}
      title={period.label}
      metric={`${formatNumber(period.records)} records`}
      preview={<MobileDensityPeriodPreview period={period} index={visualIndex} />}
    >
      <dl className="mobile-card-stats">
        <div><dt>MAPPED</dt><dd>{formatNumber(period.mapped)} / {Math.round(period.mappedShare * 100)}%</dd></div>
        <div><dt>CORPUS SHARE</dt><dd>{(period.recordShare * 100).toFixed(1)}%</dd></div>
        <div><dt>VOLUME RANK</dt><dd>#{rank} / {totalPeriods}</dd></div>
        <div><dt>SEARCH LEADS</dt><dd>{formatNumber(period.plannedQueries)}</dd></div>
      </dl>
    </MobileExpandableCard>
  );
}

function MobileDensityPeriodPreview({
  period,
  index,
}: {
  period: MobilePeriod;
  index: number;
}) {
  const volume = Math.min(1, Math.max(0.06, period.maxShare));
  const mapped = Math.min(1, Math.max(0.04, period.mappedShare));
  const volumePercent = Math.round(volume * 100);
  const mappedPercent = Math.round(mapped * 100);
  const variant = index % 5;

  if (variant === 0) {
    return (
      <span className="mobile-density-period-viz is-orbit" aria-hidden="true">
        <svg viewBox="0 0 150 62">
          <circle className="density-viz-base" cx="116" cy="31" r="24" pathLength="100" />
          <circle
            className="density-viz-volume"
            cx="116"
            cy="31"
            r="24"
            pathLength="100"
            strokeDasharray={`${volumePercent} 100`}
          />
          <circle className="density-viz-base is-inner" cx="116" cy="31" r="15" pathLength="100" />
          <circle
            className="density-viz-mapped is-inner"
            cx="116"
            cy="31"
            r="15"
            pathLength="100"
            strokeDasharray={`${mappedPercent} 100`}
          />
          <path className="density-viz-rule" d="M4 48h64M4 36h42M4 24h54" />
        </svg>
      </span>
    );
  }

  if (variant === 1) {
    const levels = [0.42, 0.72, 0.55, 1, 0.68];
    return (
      <span className="mobile-density-period-viz is-columns" aria-hidden="true">
        {levels.map((level, columnIndex) => (
          <i
            key={`${period.id}-column-${columnIndex}`}
            style={{ "--density-level": Math.max(0.16, level * volume) } as CSSProperties}
          >
            <em style={{ "--density-mapped": mapped } as CSSProperties} />
          </i>
        ))}
      </span>
    );
  }

  if (variant === 2) {
    return (
      <span className="mobile-density-period-viz is-steps" aria-hidden="true">
        <i style={{ "--density-step": Math.max(0.28, volume * 0.58) } as CSSProperties} />
        <i style={{ "--density-step": Math.max(0.42, volume * 0.78) } as CSSProperties} />
        <i style={{ "--density-step": Math.max(0.56, volume) } as CSSProperties} />
        <em style={{ "--density-mapped": mapped } as CSSProperties} />
      </span>
    );
  }

  if (variant === 3) {
    return (
      <span className="mobile-density-period-viz is-arc" aria-hidden="true">
        <svg viewBox="0 0 150 62">
          <path className="density-viz-base" pathLength="100" d="M12 53A63 63 0 0 1 138 53" />
          <path
            className="density-viz-volume"
            pathLength="100"
            strokeDasharray={`${volumePercent} 100`}
            d="M12 53A63 63 0 0 1 138 53"
          />
          <path className="density-viz-base is-inner" pathLength="100" d="M31 53a44 44 0 0 1 88 0" />
          <path
            className="density-viz-mapped is-inner"
            pathLength="100"
            strokeDasharray={`${mappedPercent} 100`}
            d="M31 53a44 44 0 0 1 88 0"
          />
        </svg>
      </span>
    );
  }

  return (
    <span className="mobile-density-period-viz is-range" aria-hidden="true">
      <svg viewBox="0 0 150 62" preserveAspectRatio="none">
        <path className="density-viz-rule" d="M4 50h142" />
        <path
          className="density-viz-range"
          d={`M5 46 L35 ${46 - (volume * 21)} L67 ${42 - (mapped * 24)} L98 ${48 - (volume * 34)} L145 ${40 - (mapped * 22)}`}
        />
        <circle className="density-viz-node" cx="35" cy={46 - (volume * 21)} r="4" />
        <circle className="density-viz-node" cx="98" cy={48 - (volume * 34)} r="4" />
      </svg>
    </span>
  );
}

function MobileAnnualSparkline({ series }: { series: Array<{ year: number; count: number }> }) {
  const titleId = useId();
  const descId = useId();
  const lineRef = useRef<SVGPolylineElement | null>(null);
  const reducedMotion = useMobilePrefersReducedMotion();
  const width = 340;
  const height = 150;
  const max = Math.max(1, ...series.map((row) => row.count));
  const minYear = Math.min(...series.map((row) => row.year));
  const maxYear = Math.max(...series.map((row) => row.year));
  const peak = series.reduce((best, row) => (row.count > best.count ? row : best), { year: minYear, count: 0 });
  const points = series.map((row) => {
    const x = ((row.year - minYear) / Math.max(1, maxYear - minYear)) * (width - 24) + 12;
    const y = height - 14 - (row.count / max) * (height - 28);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const areaPoints = `12,${height - 14} ${points} ${width - 12},${height - 14}`;
  const peakX = ((peak.year - minYear) / Math.max(1, maxYear - minYear)) * (width - 24) + 12;
  const peakY = height - 14 - (peak.count / max) * (height - 28);

  useEffect(() => {
    const line = lineRef.current;
    if (!line || reducedMotion) {
      return;
    }

    const length = line.getTotalLength();
    line.style.strokeDasharray = `${length}`;
    line.style.strokeDashoffset = `${length}`;

    const timeline = createTimeline({
      defaults: {
        ease: "outCubic",
        duration: 560,
        composition: "replace",
      },
    });
    timeline.add(line, { strokeDashoffset: [length, 0] }, 0);

    return () => {
      timeline.cancel();
      line.style.strokeDasharray = "";
      line.style.strokeDashoffset = "";
    };
  }, [points, reducedMotion]);

  return (
    <svg className="density-line-chart mobile-sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={titleId} aria-describedby={descId}>
      <title id={titleId}>Annual public record trend</title>
      <desc id={descId}>
        Dated public records from {minYear} to {maxYear}; highest annual count is {formatNumber(peak.count)} in {peak.year}.
      </desc>
      <line className="density-chart-grid" x1="12" x2={width - 12} y1={height - 14} y2={height - 14} />
      <polygon className="density-area-public" points={areaPoints} />
      <line className="density-peak-guide" x1={peakX} x2={peakX} y1={peakY} y2={height - 14} />
      <polyline ref={lineRef} className="density-line-public density-chart-path" points={points} fill="none" />
      <circle className="density-peak-dot" cx={peakX} cy={peakY} r="4.5" />
      <text className="density-chart-axis" x="12" y={height - 2}>{minYear}</text>
      <text className="density-chart-axis" x={width - 12} y={height - 2} textAnchor="end">{maxYear}</text>
    </svg>
  );
}

function MobileSourceView({ data }: { data: MobileArchiveData }) {
  const leadingFamily = data.sources.rollup[0];
  const maxFamilyRecords = Math.max(1, ...data.sources.rollup.map((row) => row.records));
  const leadingRegistry = [...data.sources.registry]
    .sort((left, right) => right.recordCount - left.recordCount)
    .slice(0, 5);
  const maxRegistryRecords = Math.max(1, ...leadingRegistry.map((row) => row.recordCount));
  const sourceOrgCells = data.sources.rollup.flatMap((row) => (
    Array.from({ length: row.orgs }, (_, index) => ({
      id: `${row.id}-${index}`,
      color: row.color,
    }))
  ));

  return (
    <div className="source-view mobile-source-view">
      <section className="source-terminal">
        <header className="source-terminal-header">
          <div className="source-header-title">
            <span>SOURCE REGISTER</span>
            <h2>Public Source Field</h2>
            <p className="source-mobile-intro">
              Public organisations and metadata roles represented in the archive.
              Restricted cultural knowledge remains outside scope.
            </p>
          </div>
        </header>
        <section className="mobile-source-visual-grid" aria-label="Source field analysis">
          <article className="mobile-source-visual-card is-family">
            <header>
              <span>FAMILY VOLUME</span>
              <strong>{formatNumber(leadingFamily?.records ?? 0)}</strong>
              <small>{leadingFamily?.label ?? "Public sources"}</small>
            </header>
            <div className="mobile-source-family-chart" aria-hidden="true">
              {data.sources.rollup.map((row) => (
                <span key={row.id}>
                  <i
                    style={{
                      "--source-volume": row.records / maxFamilyRecords,
                      "--source-color": row.color,
                    } as CSSProperties}
                  />
                  <b>{row.orgs}</b>
                </span>
              ))}
            </div>
            <p>{data.sources.rollup.length} source families · numbers show organisations per family</p>
          </article>

          <article className="mobile-source-visual-card is-orgs">
            <header>
              <span>ORGANISATION FIELD</span>
              <strong>{formatNumber(data.sources.metrics.sourceOrgs)}</strong>
              <small>registered public sources</small>
            </header>
            <div className="mobile-source-org-matrix" aria-hidden="true">
              {sourceOrgCells.map((cell) => (
                <i key={cell.id} style={{ "--source-color": cell.color } as CSSProperties} />
              ))}
            </div>
          </article>

          <article className="mobile-source-visual-card is-register">
            <header>
              <span>LEADING REGISTER</span>
              <strong>{formatNumber(leadingRegistry[0]?.recordCount ?? 0)}</strong>
              <small>{leadingRegistry[0]?.name ?? "Registered source"}</small>
            </header>
            <div className="mobile-source-register-chart" aria-hidden="true">
              {leadingRegistry.map((row, index) => (
                <span key={row.id}>
                  <i style={{ "--source-volume": row.recordCount / maxRegistryRecords } as CSSProperties} />
                  <b>{String(index + 1).padStart(2, "0")}</b>
                </span>
              ))}
            </div>
          </article>
        </section>
        <MobileCardDeck className="source-mobile-accordions">
          <MobileExpandableCard
            cardId="source-lists"
            className="source-mobile-accordion"
            tone="blue"
            eyebrow="SOURCE DETAIL"
            title="Source Lists"
            metric={`${data.sources.rollup.length} families · ${data.sources.metrics.sourceTypes} types`}
            preview={(
              <span className="mobile-preview-bars" aria-hidden="true">
                {data.sources.rollup.map((row) => (
                  <i
                    key={row.id}
                    style={{ "--preview-progress": row.records / maxFamilyRecords } as CSSProperties}
                  />
                ))}
              </span>
            )}
          >
            <section className="mobile-source-list-group">
              <h3>Source Families</h3>
              <div className="source-pane-scroll">
                {data.sources.rollup.map((row) => (
                  <div className="source-rollup-row" key={row.id}>
                    <i style={{ "--source-color": row.color } as CSSProperties} />
                    <span>
                      <b>{row.label}</b>
                      <small>{formatNumber(row.orgs)} organisations</small>
                    </span>
                    <strong>{formatNumber(row.records)}</strong>
                  </div>
                ))}
              </div>
            </section>
            <section className="mobile-source-list-group">
              <h3>Public Roles</h3>
              <div className="source-pane-scroll">
                {data.sources.typeRows.slice(0, 12).map((row) => (
                  <div className="source-rollup-row" key={row.id}>
                    <i style={{ "--source-color": row.color } as CSSProperties} />
                    <span>
                      <b>{row.label}</b>
                      <small>{row.familyLabel} · {formatNumber(row.orgs)} organisations</small>
                    </span>
                    <strong>{formatNumber(row.records)}</strong>
                  </div>
                ))}
              </div>
            </section>
            <section className="mobile-source-list-group">
              <h3>Registered Sources</h3>
              <div className="source-registry-scroll">
                {data.sources.registry.slice(0, 12).map((row) => (
                  <div className="source-registry-row" key={row.id}>
                    <span>
                      <b>{row.name}</b>
                      <small>{row.publicRole} · {row.familyLabel} · {row.displayType}</small>
                    </span>
                    <strong>{formatNumber(row.recordCount)}</strong>
                  </div>
                ))}
              </div>
            </section>
            <p className="mobile-card-note">The desktop register retains the full inspector and detailed source metadata.</p>
          </MobileExpandableCard>
        </MobileCardDeck>
      </section>
    </div>
  );
}

function MobileAboutView({ data }: { data: MobileArchiveData }) {
  const mappedShare = data.summary.mappedRecordCount / Math.max(1, data.summary.recordCount);
  const mappedCells = Math.round(mappedShare * 10);
  const maxSourceOrgs = Math.max(1, ...data.sources.rollup.map((row) => row.orgs));

  return (
    <div className="about-view mobile-about-view">
      <header className="mobile-about-heading">
        <span>ABOUT</span>
        <h1>About AusFigures</h1>
        <p>AusFigures is a source-grounded public-text archive for tracing how humanoid or humanoid-adjacent supernatural figures appear in Australian public sources.</p>
        <div className="mobile-hero-badges" aria-label="Project qualities">
          <span><i aria-hidden="true" />public text</span>
          <span><i aria-hidden="true" />auditable</span>
          <span><i aria-hidden="true" />Australia</span>
        </div>
      </header>
      <section className="about-status-panel">
        <header className="about-status-head">
          <i aria-hidden="true" />
          <span>DATA STATUS / PUBLIC CORPUS</span>
        </header>
        <div className="about-status-grid">
          <div className="is-public">
            <span>PUBLIC RECORDS</span>
            <b>{formatNumber(data.summary.recordCount)}</b>
            <i className="about-status-register" aria-hidden="true">
              {Array.from({ length: 10 }, (_, index) => <em key={index} />)}
            </i>
          </div>
          <div className="is-mapped">
            <span>MAPPED RECORDS</span>
            <b>{formatNumber(data.summary.mappedRecordCount)}</b>
            <i className="about-status-register" aria-hidden="true">
              {Array.from({ length: 10 }, (_, index) => (
                <em className={index < mappedCells ? "is-active" : ""} key={index} />
              ))}
            </i>
          </div>
          <div className="is-source">
            <span>SOURCE ORGS</span>
            <b>{formatNumber(data.summary.sourceCount)}</b>
            <i className="about-status-source-bars" aria-hidden="true">
              {data.sources.rollup.map((row) => (
                <em
                  key={row.id}
                  style={{ "--about-source-share": row.orgs / maxSourceOrgs } as CSSProperties}
                />
              ))}
            </i>
          </div>
        </div>
      </section>
      <MobileCardDeck className="about-grid">
        <MobileAboutModule
          cardId="about-scope"
          title="Scope"
          tone="mint"
          preview={(
            <span className="mobile-about-scope-preview" aria-label={`${data.figures.length} figures, ${data.density.periods.length} periods and 8 regions`}>
              <span>
                <b>{formatNumber(data.figures.length)}</b>
                <small>FIGURES</small>
                <i className="about-scope-figure-grid" aria-hidden="true">
                  {Array.from({ length: 14 }, (_, index) => <em key={index} />)}
                </i>
              </span>
              <span>
                <b>{formatNumber(data.density.periods.length)}</b>
                <small>PERIODS</small>
                <i className="about-scope-period-bars" aria-hidden="true">
                  {data.density.periods.map((period) => (
                    <em
                      key={period.id}
                      style={{ "--about-period-share": period.maxShare } as CSSProperties}
                    />
                  ))}
                </i>
              </span>
              <span>
                <b>8</b>
                <small>REGIONS</small>
                <i className="about-scope-region-grid" aria-hidden="true">
                  {Array.from({ length: 8 }, (_, index) => <em key={index} />)}
                </i>
              </span>
            </span>
          )}
        >
          <p>
            It records published encounters, apparition accounts, ghost and local legends,
            traditional and spirit-person narratives, retellings, and related public discourse
            as source-grounded public records.
          </p>
        </MobileAboutModule>
        <MobileAboutModule cardId="about-method" title="Method And Rigour" tone="coral">
          <ol className="mobile-about-sequence">
            <li><b>01</b><span>Discover a stable public trace.</span></li>
            <li><b>02</b><span>Preserve source, date, role and publicness.</span></li>
            <li><b>03</b><span>Classify figure, narrative, period and place separately.</span></li>
            <li><b>04</b><span>Publish a map flag only after location review.</span></li>
          </ol>
          <dl className="mobile-about-checks">
            <div><dt>LAYER SEPARATION</dt><dd>Public records, map flags, metadata-only items and leads remain distinct.</dd></div>
            <div><dt>REVISION</dt><dd>The corpus is auditable and revisable, not a complete authority.</dd></div>
          </dl>
        </MobileAboutModule>
        <MobileAboutModule cardId="about-limits" title="Limits And Ethics" tone="yellow">
          <p>
            Public source exists does not mean a supernatural claim is verified. Map markers are
            reviewed display locations for records, not habitats, populations, or proof.
          </p>
          <p>
            Indigenous-related records require careful handling of terminology, source voice,
            publicness, cultural sensitivity and display mode. Restricted or private knowledge is
            outside the public archive scope.
          </p>
        </MobileAboutModule>
        <MobileAboutModule cardId="about-repository" title="Open Project" tone="blue">
          <p>
            Source code, data policies and revision history are available in the public repository.
          </p>
          <a
            className="mobile-about-repository-link"
            href="https://github.com/dpan538/australian-humanoid-supernatural-texts"
            target="_blank"
            rel="noreferrer"
          >
            View GitHub repository <span aria-hidden="true">↗</span>
          </a>
        </MobileAboutModule>
      </MobileCardDeck>
    </div>
  );
}

function MobileAboutModule({
  cardId,
  title,
  tone,
  preview,
  defaultOpen = false,
  children,
}: {
  cardId: string;
  title: string;
  tone: (typeof MOBILE_CARD_TONES)[number];
  preview?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <MobileExpandableCard
      cardId={cardId}
      className="about-module about-accordion-module"
      tone={tone}
      eyebrow="RESEARCH NOTE"
      title={title}
      preview={preview}
      defaultOpen={defaultOpen}
    >
      <div className="mobile-about-copy">{children}</div>
    </MobileExpandableCard>
  );
}

type MobileCardDeckValue = {
  activeId: string | null;
  setActiveId: Dispatch<SetStateAction<string | null>>;
};

const MobileCardDeckContext = createContext<MobileCardDeckValue | null>(null);

export function MobileCardDeck({
  children,
  className = "",
  defaultOpenId = null,
}: {
  children: ReactNode;
  className?: string;
  defaultOpenId?: string | null;
}) {
  const [activeId, setActiveId] = useState<string | null>(defaultOpenId);
  const value = useMemo(() => ({ activeId, setActiveId }), [activeId]);

  return (
    <MobileCardDeckContext.Provider value={value}>
      <div className={`mobile-card-deck ${className}`.trim()}>{children}</div>
    </MobileCardDeckContext.Provider>
  );
}

export function MobileExpandableCard({
  cardId,
  className = "",
  tone,
  eyebrow,
  title,
  metric,
  preview,
  defaultOpen = false,
  children,
}: {
  cardId: string;
  className?: string;
  tone: MobileCardTone;
  eyebrow: string;
  title: string;
  metric?: string;
  preview?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const cardDeck = useContext(MobileCardDeckContext);
  const [localOpen, setLocalOpen] = useState(defaultOpen);
  const open = cardDeck ? cardDeck.activeId === cardId : localOpen;
  const reducedMotion = useMobilePrefersReducedMotion();
  const cardRef = useRef<HTMLElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const mounted = useRef(false);
  const panelId = useId();

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) {
      return;
    }

    if (!mounted.current) {
      panel.style.height = open ? "auto" : "0px";
      panel.style.opacity = open ? "1" : "0";
      mounted.current = true;
      return;
    }

    const from = panel.getBoundingClientRect().height;
    const to = open ? panel.scrollHeight : 0;
    if (reducedMotion) {
      panel.style.height = open ? "auto" : "0px";
      panel.style.opacity = open ? "1" : "0";
      return;
    }

    panel.style.height = `${from}px`;
    panel.style.overflow = "hidden";
    const timeline = createTimeline({
      defaults: {
        ease: "inOutCubic",
        duration: 520,
        composition: "replace",
      },
    });
    if (cardRef.current) {
      timeline.add(cardRef.current, {
        scale: open ? [0.988, 1] : [1, 0.994, 1],
        duration: open ? 420 : 320,
      }, 0);
    }
    timeline.add(panel, {
      height: [from, to],
      opacity: open ? [0.48, 1] : [1, 0],
      translateY: open ? [8, 0] : [0, -4],
    }, 0);
    const contentItems = panel.querySelectorAll(".mobile-expand-content > *");
    if (open && contentItems.length) {
      timeline.add(contentItems, {
        opacity: [0, 1],
        translateY: [12, 0],
        delay: stagger(34),
        duration: 360,
      }, 90);
    }
    const completionTimer = window.setTimeout(() => {
      panel.style.height = open ? "auto" : "0px";
      panel.style.overflow = "hidden";
      panel.style.transform = "";
      if (open) {
        cardRef.current?.scrollIntoView({
          behavior: reducedMotion ? "auto" : "smooth",
          block: "nearest",
          inline: "nearest",
        });
      }
    }, 560);

    return () => {
      window.clearTimeout(completionTimer);
      timeline.cancel();
    };
  }, [open, reducedMotion]);

  return (
    <article
      ref={cardRef}
      className={`mobile-expand-card ${className} ${preview ? "has-preview" : ""} ${open ? "is-open" : ""}`.trim()}
      data-tone={tone}
      data-card-id={cardId}
    >
      <button
        type="button"
        className="mobile-expand-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          if (cardDeck) {
            cardDeck.setActiveId((current) => current === cardId ? null : cardId);
            return;
          }
          setLocalOpen((current) => !current);
        }}
      >
        <span className="mobile-expand-title">
          <small>{eyebrow}</small>
          <b>{title}</b>
        </span>
        {metric ? <strong>{metric}</strong> : null}
        {preview ? <span className="mobile-expand-preview">{preview}</span> : null}
        <i className="mobile-expand-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" focusable="false">
            <path d="m6.5 9 5.5 5.5L17.5 9" />
          </svg>
        </i>
      </button>
      <div
        ref={panelRef}
        id={panelId}
        className="mobile-expand-panel"
        role="region"
        aria-hidden={!open}
        inert={!open}
      >
        <div className="mobile-expand-content">{children}</div>
      </div>
    </article>
  );
}

function addMobileTimelineTargets(
  timeline: Timeline,
  targets: NodeListOf<Element> | Element[],
  params: AnimationParams,
  position: number,
) {
  if (targets.length > 0) {
    timeline.add(targets, params, position);
  }
}

export function MobileArchiveControls({ view }: { view: MobileControlView }) {
  const controlsRef = useRef<HTMLDivElement | null>(null);
  const spotlightRef = useRef<HTMLSpanElement | null>(null);
  const previousSpotlightX = useRef<number | null>(null);
  const reducedMotion = useMobilePrefersReducedMotion();
  const handleNavPress = useCallback((event: PointerEvent<HTMLAnchorElement>) => {
    if (reducedMotion) {
      return;
    }
    const target = event.currentTarget;
    target.classList.remove("is-pressing");
    void target.offsetWidth;
    target.classList.add("is-pressing");
    window.setTimeout(() => target.classList.remove("is-pressing"), 420);
  }, [reducedMotion]);

  useEffect(() => {
    const controls = controlsRef.current;
    const spotlight = spotlightRef.current;
    if (!controls || !spotlight) {
      return;
    }

    let timeline: Timeline | null = null;
    const positionSpotlight = () => {
      const active = controls.querySelector<HTMLElement>(".mobile-archive-link.is-active");
      if (!active) {
        spotlight.style.opacity = "0";
        previousSpotlightX.current = null;
        return;
      }
      spotlight.style.opacity = "1";
      const controlsBox = controls.getBoundingClientRect();
      const activeBox = active.getBoundingClientRect();
      const controlsInnerOffset = controls.clientLeft;
      const nextX = activeBox.left
        - controlsBox.left
        - controlsInnerOffset
        + activeBox.width / 2
        - spotlight.offsetWidth / 2;
      let storedView: string | null = null;
      try {
        storedView = window.sessionStorage.getItem(MOBILE_NAV_STORAGE_KEY);
      } catch {
        storedView = null;
      }
      const previousLink = storedView
        ? Array.from(controls.querySelectorAll<HTMLElement>(".mobile-archive-link"))
          .find((link) => link.dataset.navView === storedView)
        : null;
      const previousBox = previousLink?.getBoundingClientRect();
      const storedX = previousBox
        ? previousBox.left
          - controlsBox.left
          - controlsInnerOffset
          + previousBox.width / 2
          - spotlight.offsetWidth / 2
        : nextX;
      const fromX = previousSpotlightX.current ?? storedX;
      previousSpotlightX.current = nextX;
      try {
        window.sessionStorage.setItem(MOBILE_NAV_STORAGE_KEY, view);
      } catch {
        // Session storage is optional; visual navigation remains functional without it.
      }
      if (reducedMotion) {
        spotlight.style.transform = `translate3d(${nextX}px, 0, 0)`;
        return;
      }
      timeline?.cancel();
      timeline = createTimeline({
        defaults: {
          ease: "outQuint",
          duration: 560,
          composition: "replace",
        },
      });
      timeline.add(spotlight, {
        translateX: [fromX, nextX],
        scaleX: [0.62, 1],
        opacity: [0.42, 1],
      }, 0);
      const activeIcon = active.querySelector(".mobile-nav-icon");
      if (activeIcon) {
        timeline.add(activeIcon, {
          opacity: [0.46, 1],
          translateY: [5, -2],
          scale: [0.76, 1.12],
          rotate: [-5, 0],
          duration: 460,
        }, 40);
      }
    };

    positionSpotlight();
    window.addEventListener("resize", positionSpotlight);
    return () => {
      window.removeEventListener("resize", positionSpotlight);
      timeline?.cancel();
    };
  }, [reducedMotion, view]);

  return (
    <div
      ref={controlsRef}
      className="mobile-archive-controls"
      aria-label="Mobile archive controls"
    >
      <span ref={spotlightRef} className="mobile-nav-spotlight" aria-hidden="true" />
      <div className="mobile-archive-expanded">
        <nav className="mobile-archive-nav" aria-label="Mobile archive navigation">
          {MOBILE_NAV_ITEMS.map((item) => (
            <Link
              key={item.view}
              className={view === item.view ? "mobile-archive-link is-active" : "mobile-archive-link"}
              href={item.href}
              data-nav-view={item.view}
              aria-label={`Open ${item.label}`}
              aria-current={view === item.view ? "page" : undefined}
              onPointerDown={handleNavPress}
            >
              <MobileNavIcon name={item.icon} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}

function useMobilePrefersReducedMotion() {
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

function readStoredTheme(): DisplayTheme {
  if (typeof window === "undefined") {
    return "dark";
  }
  try {
    const stored = window.sessionStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
      return stored;
    }
  } catch {
    return "dark";
  }
  return "dark";
}

function MobileThemeControl() {
  const [theme, setTheme] = useState<DisplayTheme>("dark");
  const [hydrated, setHydrated] = useState(false);
  const [switching, setSwitching] = useState(false);
  const completionTimerRef = useRef<number | null>(null);
  const reducedMotion = useMobilePrefersReducedMotion();

  useEffect(() => {
    const storedTheme = readStoredTheme();
    setTheme(storedTheme);
    document.documentElement.dataset.theme = storedTheme;
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    document.documentElement.dataset.theme = theme;
    window.sessionStorage.setItem(THEME_STORAGE_KEY, theme);
    window.dispatchEvent(new CustomEvent("archive-display-change", { detail: { theme } }));
  }, [theme, hydrated]);

  useEffect(() => () => {
    if (completionTimerRef.current !== null) {
      window.clearTimeout(completionTimerRef.current);
    }
  }, []);

  return (
    <button
      type="button"
      className={`mobile-top-action mobile-top-theme mobile-theme-button ${switching ? "is-switching" : ""}`.trim()}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      aria-pressed={theme === "light"}
      onClick={(event) => {
        if (switching) {
          return;
        }
        const nextTheme = theme === "dark" ? "light" : "dark";
        const icon = event.currentTarget.querySelector(".mobile-theme-icon");
        setSwitching(true);
        if (!reducedMotion && icon) {
          const iconTimeline = createTimeline({
            defaults: {
              ease: "outQuint",
              composition: "replace",
            },
          });
          iconTimeline.add(icon, {
            rotate: nextTheme === "light" ? [-26, 0] : [24, 0],
            scale: [0.72, 1],
            opacity: [0.52, 1],
            duration: 460,
          }, 0);
        }
        runThemeTransition(event.currentTarget, nextTheme, () => {
          document.documentElement.dataset.theme = nextTheme;
          setTheme(nextTheme);
        });
        completionTimerRef.current = window.setTimeout(() => {
          setSwitching(false);
          completionTimerRef.current = null;
        }, 720);
      }}
    >
      <MobileNavIcon name="theme" theme={theme} />
      <span>{theme === "dark" ? "Dark" : "Light"}</span>
    </button>
  );
}

function MobileNavIcon({ name, theme }: { name: MobileNavName; theme?: DisplayTheme }) {
  if (name === "theme") {
    if (theme === "light") {
      return (
        <svg
          className="mobile-nav-icon mobile-theme-icon"
          data-theme-icon="sun"
          viewBox="0 0 24 24"
          aria-hidden="true"
          focusable="false"
        >
          <circle className="mobile-theme-core" cx="12" cy="12" r="3.6" />
          <g className="mobile-theme-rays">
            <path d="M12 2.7v2.2" />
            <path d="M12 19.1v2.2" />
            <path d="M2.7 12h2.2" />
            <path d="M19.1 12h2.2" />
            <path d="m5.4 5.4 1.6 1.6" />
            <path d="m17 17 1.6 1.6" />
            <path d="m18.6 5.4-1.6 1.6" />
            <path d="m7 17-1.6 1.6" />
          </g>
        </svg>
      );
    }
    return (
      <svg
        className="mobile-nav-icon mobile-theme-icon"
        data-theme-icon="moon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <g className="mobile-theme-rays">
          <path d="M12 2.7v2.2" />
          <path d="M12 19.1v2.2" />
          <path d="M2.7 12h2.2" />
          <path d="M19.1 12h2.2" />
          <path d="m5.4 5.4 1.6 1.6" />
          <path d="m17 17 1.6 1.6" />
          <path d="m18.6 5.4-1.6 1.6" />
          <path d="m7 17-1.6 1.6" />
        </g>
        <path className="mobile-theme-core" d="M18.2 15.8A7.6 7.6 0 0 1 8.2 5.2 7.7 7.7 0 1 0 18.2 15.8Z" />
      </svg>
    );
  }

  if (name === "about") {
    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="m6.5 18.5 4.7-13h1.6l4.7 13M8.5 13.2h7" />
      </svg>
    );
  }

  if (name === "figures") {
    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M7.4 3.8h9.8c1 0 1.8.8 1.8 1.8v13.1c0 .9-.7 1.6-1.6 1.6H7.8A2.8 2.8 0 0 1 5 17.5V6.6a2.8 2.8 0 0 1 2.4-2.8Z" />
        <path d="M5 17.5c0-1.4 1.1-2.5 2.5-2.5H19M8.9 12.5l2.1-5.7h1.4l2.1 5.7M9.7 10.4h4" />
      </svg>
    );
  }

  if (name === "source") {
    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M9.6 14.4 14.4 9.6" />
        <path d="M8.6 11.1 7.3 12.4a3 3 0 0 0 4.3 4.3l1.3-1.3" />
        <path d="M15.4 12.9 16.7 11.6a3 3 0 0 0-4.3-4.3l-1.3 1.3" />
      </svg>
    );
  }

  if (name === "density") {
    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M6 18.2h12" />
        <path d="M8 15.8V10" />
        <path d="M12 15.8V6.8" />
        <path d="M16 15.8v-4.2" />
      </svg>
    );
  }

  return (
    <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M5.2 7.3 9.5 5.4l5 2 4.3-1.9v11.2l-4.3 1.9-5-2-4.3 1.9z" />
      <path d="M9.5 5.4v11.2" />
      <path d="M14.5 7.4v11.2" />
    </svg>
  );
}
