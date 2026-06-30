"use client";

import type { CSSProperties, FocusEvent, KeyboardEvent, PointerEvent, ReactNode, RefObject, SyntheticEvent } from "react";
import Link from "next/link";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createTimeline, stagger } from "animejs";
import type { Timeline } from "animejs";
import { STATE_SHAPES } from "@/lib/au-map-data";
import type { FrontendData, MapFlagItem, RecordItem } from "@/lib/types";
import { SOURCE_FAMILY_STYLES, buildSourceRegistryData, displaySourceType, sourceFamilyId, type SourceFamilyId } from "@/lib/source-view-data";

type MobileControlView = "about" | "map" | "density" | "dashboard" | "source";
type DisplayTheme = "dark" | "light";
type MobileNavName = "theme" | "about" | "source" | "density" | "map";
const MOBILE_ARCHIVE_QUERY = "(max-width: 980px), (pointer: coarse)";
const MOBILE_NAV_IDLE_MS = 4600;
const THEME_STORAGE_KEY = "aus-archive-theme";
const MOBILE_MAP_VIEWBOX = { x: 24, y: 18, width: 930, height: 682 } as const;
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

type MobileRouteView = "about" | "map" | "density" | "source";

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
  ACT: [784, 512],
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
      sourceCount: data.summary.source_count || data.sources.length,
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
  };
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

function isMobileArchiveViewport() {
  return typeof window !== "undefined" && window.matchMedia(MOBILE_ARCHIVE_QUERY).matches;
}

function isFineHoverPointer() {
  return typeof window !== "undefined" && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
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
  const router = useRouter();
  const [blockedDashboard, setBlockedDashboard] = useState(() => view === "dashboard" && isMobileArchiveViewport());

  useEffect(() => {
    if (view !== "dashboard") {
      setBlockedDashboard(false);
      return;
    }

    const mediaQuery = window.matchMedia(MOBILE_ARCHIVE_QUERY);
    const syncRoute = () => {
      const shouldBlock = mediaQuery.matches;
      setBlockedDashboard(shouldBlock);
      if (shouldBlock) {
        router.replace("/map");
      }
    };

    syncRoute();
    mediaQuery.addEventListener("change", syncRoute);
    return () => mediaQuery.removeEventListener("change", syncRoute);
  }, [router, view]);

  return { blockedDashboard };
}

export function MobileArchiveRoute({ view, data }: { view: MobileControlView; data: FrontendData }) {
  const routeView: MobileRouteView = view === "dashboard" ? "map" : view;
  const mobileData = useMemo(() => buildMobileArchiveData(data), [data]);
  const pageRef = useRef<HTMLElement | null>(null);
  const reducedMotion = useMobilePrefersReducedMotion();

  useMobilePageAmbientMotion(pageRef, routeView, reducedMotion);

  return (
    <main className={`terminal-shell mobile-archive-shell mobile-view-${routeView}`}>
      <h1 className="visually-hidden">{mobileRouteHeading(routeView)}</h1>
      <div className="noise-layer" aria-hidden="true" />
      <section ref={pageRef} className="mobile-archive-page" aria-label={`AusFigures ${routeView} mobile view`}>
        {routeView === "map" ? <MobileMapView data={mobileData} /> : null}
        {routeView === "density" ? <MobileDensityView data={mobileData} /> : null}
        {routeView === "source" ? <MobileSourceView data={mobileData} /> : null}
        {routeView === "about" ? <MobileAboutView data={mobileData} /> : null}
      </section>
      <MobileArchiveControls view={routeView} />
    </main>
  );
}

function useMobilePageAmbientMotion(
  rootRef: RefObject<HTMLElement | null>,
  view: MobileRouteView,
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
    const mapDots = Array.from(root.querySelectorAll<SVGCircleElement>(".mobile-map-canvas .record-flag-dot"));
    const ambientMapDots = mapDots.filter((_, index) => index % 29 === 0);
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

    let redrawTimeline: Timeline | null = null;
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
        root.querySelectorAll(".mobile-map-heading, .density-header, .source-terminal-header, .mobile-about-heading"),
        { opacity: [0.74, 1] },
        0,
      );
      addMobileTimelineTargets(
        redrawTimeline,
        root.querySelectorAll(".readout-block, .state-mini, .density-band, .density-chart-card, .source-mobile-accordion, .about-status-panel, .about-module"),
        { opacity: [0.76, 1], delay: stagger(28) },
        80,
      );
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

    let ambientTimeline: Timeline | null = null;
    let ambientTimer: number | null = null;
    const startAmbient = () => {
      ambientTimeline?.cancel();
      ambientTimeline = createTimeline({
        loop: true,
        alternate: true,
        defaults: {
          ease: "inOutSine",
          duration: 6800,
          composition: "replace",
        },
      });

      if (view === "map") {
        addMobileTimelineTargets(ambientTimeline, root.querySelectorAll(".coast-outline"), { opacity: [0.62, 1] }, 0);
        addMobileTimelineTargets(ambientTimeline, ambientMapDots, {
          opacity: [0.62, 1],
          scale: [0.92, 1.14],
          delay: stagger(38),
        }, 0);
        addMobileTimelineTargets(ambientTimeline, root.querySelectorAll(".map-readout-led"), {
          opacity: [0.28, 0.96],
          scale: [0.86, 1.14],
        }, 180);
      }

      if (view === "density") {
        root.querySelectorAll<HTMLElement>(".density-bar-fill").forEach((target) => {
          target.style.transformOrigin = "left center";
        });
        addMobileTimelineTargets(ambientTimeline, root.querySelectorAll(".density-bar-fill"), {
          opacity: [0.56, 1],
          scaleX: [0.955, 1.035],
          delay: stagger(34),
        }, 0);
        addMobileTimelineTargets(ambientTimeline, root.querySelectorAll(".density-chart-path"), { opacity: [0.5, 1] }, 180);
      }

      if (view === "source") {
        addMobileTimelineTargets(ambientTimeline, root.querySelectorAll(".source-mobile-accordion"), { opacity: [0.82, 1] }, 0);
        addMobileTimelineTargets(ambientTimeline, root.querySelectorAll(".source-rollup-row i"), {
          opacity: [0.32, 1],
          scale: [0.86, 1.12],
          delay: stagger(64),
        }, 180);
      }

      if (view === "about") {
        addMobileTimelineTargets(ambientTimeline, root.querySelectorAll(".about-status-panel, .about-module"), { opacity: [0.82, 1] }, 0);
        addMobileTimelineTargets(ambientTimeline, root.querySelectorAll(".about-status-head i, .about-module-head i"), {
          opacity: [0.32, 1],
          scale: [0.86, 1.14],
          delay: stagger(140),
        }, 180);
      }
    };
    const stopAmbient = () => {
      if (ambientTimer) {
        window.clearTimeout(ambientTimer);
        ambientTimer = null;
      }
      ambientTimeline?.cancel();
      ambientTimeline = null;
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        startAmbient();
      } else {
        stopAmbient();
      }
    };

    ambientTimer = window.setTimeout(startAmbient, view === "map" ? 1700 : 520);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.cancelAnimationFrame(redrawFrame);
      redrawTimeline?.cancel();
      stopAmbient();
      resetRedrawTargets();
      resetMapDots();
    };
  }, [reducedMotion, rootRef, view]);
}

function mobileRouteHeading(view: MobileRouteView) {
  if (view === "density") {
    return "AusFigures density explorer";
  }
  if (view === "source") {
    return "AusFigures source register";
  }
  if (view === "about") {
    return "About AusFigures";
  }
  return "AusFigures public map";
}

function MobileMapView({ data }: { data: MobileArchiveData }) {
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const titleId = useId();
  const descId = useId();
  const touchStateHandled = useRef(false);
  const stateCounts = data.map.stateCounts;
  const stateCountMap = new Map(stateCounts.map((row) => [row.code, row.count]));
  const activeState = selectedState ? STATE_NAMES[selectedState] ?? selectedState : "Australia";
  const activeCount = selectedState ? stateCountMap.get(selectedState) ?? 0 : data.summary.mappedRecordCount;
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

  return (
    <div className="map-view mobile-map-view">
      <header className="mobile-map-heading">
        <span>PUBLIC MAP</span>
        <b>Public display locations</b>
      </header>
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
            Australia map with state and territory outlines, summarising {formatNumber(data.summary.mappedRecordCount)} mapped public records.
          </desc>
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
          <path className="coast-outline" d={STATE_SHAPES.map((state) => state.d).join(" ")} />
          <g className={`record-flag-layer ${selectedState ? "has-state-selected" : ""}`} aria-hidden="true">
            {data.map.flags.map((flag) => (
              <MobileMapFlagMarker key={flag.id} flag={flag} stateLinked={selectedState === flag.state} />
            ))}
          </g>
          <g className="state-label-layer" aria-hidden="true">
            {STATE_SHAPES.map((state) => {
              const label = STATE_LABEL_OVERRIDES[state.code] ?? state.label;
              return (
                <text
                  key={`mobile-label-${state.code}`}
                  className={`state-label state-label-${state.code.toLowerCase()}`}
                  x={label[0]}
                  y={label[1]}
                >
                  {state.code}
                </text>
              );
            })}
          </g>
        </svg>
      </div>
      <p className="mobile-map-note">{data.map.interpretation}</p>
      <aside className="map-readout">
        <div className="readout-block">
          <i className="map-readout-led" aria-hidden="true" />
          <span className="tiny-label">REGION</span>
          <strong>{activeState}</strong>
          <span className="readout-number">{formatNumber(activeCount)}</span>
          <span className="readout-tail">mapped records</span>
        </div>
        <div className="readout-grid">
          {stateCounts.map((row) => (
            <button
              type="button"
              className={selectedState === row.code ? "state-mini active" : "state-mini"}
              key={row.code}
              onClick={() => toggleSelectedState(row.code)}
              aria-pressed={selectedState === row.code}
              aria-label={`${STATE_NAMES[row.code] ?? row.code}, ${formatNumber(row.count)} mapped records`}
            >
              <span>{row.code}</span>
              <b>{formatNumber(row.count)}</b>
            </button>
          ))}
        </div>
        <div className="map-health-note">
          <span>MAPPED RECORDS</span>
          <b>{formatNumber(data.summary.mappedRecordCount)}</b>
          <small>{formatNumber(data.summary.mappedRecordCount)} mapped / {formatNumber(data.summary.recordCount)} public records</small>
          <em>one display marker per mapped public record</em>
        </div>
      </aside>
    </div>
  );
}

function MobileMapFlagMarker({ flag, stateLinked }: { flag: MobileMapFlag; stateLinked: boolean }) {
  const className = ["record-flag", "precise", flag.toneClass, stateLinked ? "state-linked" : ""].filter(Boolean).join(" ");

  return (
    <g className={className} aria-hidden="true">
      <circle className="record-flag-dot" cx={flag.displayX} cy={flag.displayY} r={stateLinked ? 4.1 : 3.25} />
    </g>
  );
}

function MobileDensityView({ data }: { data: MobileArchiveData }) {
  return (
    <div className="density-view mobile-density-view">
      <header className="density-header">
        <div>
          <span>TIME DENSITY</span>
          <p>Density shows public-text record distribution and source coverage. It is not a claim about real-world frequency.</p>
        </div>
        <b>
          {data.summary.earliestYear}-{data.summary.latestYear} / {formatNumber(data.summary.recordCount)} PUBLIC RECORDS / {formatNumber(data.summary.mappedRecordCount)} MAPPED
        </b>
      </header>
      <div className="density-bands">
        {data.density.periods.map((period) => (
          <MobileDensityBand key={period.id} period={period} />
        ))}
      </div>
      <article className="density-chart-card mobile-density-trend">
        <header>
          <span>ANNUAL TREND</span>
          <b>Dated public records by year</b>
        </header>
        <MobileAnnualSparkline series={data.density.annualSeries} />
        <p>Use the desktop view for the full analytical density console.</p>
      </article>
    </div>
  );
}

function MobileDensityBand({ period }: { period: MobilePeriod }) {
  return (
    <article className="density-band">
      <div className="band-meta">
        <span>{period.label}</span>
        <b>{formatNumber(period.records)}</b>
        <small>{formatNumber(period.mapped)} mapped / {Math.round(period.mappedShare * 100)}%</small>
      </div>
      <div className="density-band-bars" aria-hidden="true">
        <i className="density-bar-fill" style={{ "--bar-width": `${Math.round(period.maxShare * 100)}%` } as CSSProperties} />
        <em className="density-bar-fill" style={{ "--bar-width": `${Math.round(period.mappedShare * 100)}%` } as CSSProperties} />
      </div>
      <span className="density-band-action">{formatNumber(period.plannedQueries)} planned queries</span>
    </article>
  );
}

function MobileAnnualSparkline({ series }: { series: Array<{ year: number; count: number }> }) {
  const titleId = useId();
  const descId = useId();
  const lineRef = useRef<SVGPolylineElement | null>(null);
  const reducedMotion = useMobilePrefersReducedMotion();
  const width = 340;
  const height = 112;
  const max = Math.max(1, ...series.map((row) => row.count));
  const minYear = Math.min(...series.map((row) => row.year));
  const maxYear = Math.max(...series.map((row) => row.year));
  const peak = series.reduce((best, row) => (row.count > best.count ? row : best), { year: minYear, count: 0 });
  const points = series.map((row) => {
    const x = ((row.year - minYear) / Math.max(1, maxYear - minYear)) * (width - 24) + 12;
    const y = height - 14 - (row.count / max) * (height - 28);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

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
      <polyline ref={lineRef} className="density-line-public density-chart-path" points={points} fill="none" />
      <text className="density-chart-axis" x="12" y={height - 2}>{minYear}</text>
      <text className="density-chart-axis" x={width - 12} y={height - 2} textAnchor="end">{maxYear}</text>
    </svg>
  );
}

function MobileSourceView({ data }: { data: MobileArchiveData }) {
  const reducedMotion = useMobilePrefersReducedMotion();
  const handleDetailsToggle = useCallback((event: SyntheticEvent<HTMLDetailsElement>) => {
    animateMobileDetails(event.currentTarget, reducedMotion);
  }, [reducedMotion]);

  return (
    <div className="source-view mobile-source-view">
      <section className="source-terminal">
        <header className="source-terminal-header">
          <div className="source-header-title">
            <span>SOURCE REGISTER</span>
            <h2>Public Source Field</h2>
            <p className="source-mobile-intro">
              AusFigures organises public source organisations and public metadata signals used by the archive. These rows describe source context, not permission to extract restricted cultural knowledge.
            </p>
          </div>
          <div className="source-header-status" aria-label="Source metrics">
            <i aria-hidden="true" />
            <div className="source-metric-cell"><span>SOURCE ORGS</span><b>{formatNumber(data.sources.metrics.sourceOrgs)}</b></div>
            <div className="source-metric-cell"><span>PUBLIC RECORDS</span><b>{formatNumber(data.sources.metrics.publicRecords)}</b></div>
            <div className="source-metric-cell"><span>SOURCE TYPES</span><b>{formatNumber(data.sources.metrics.sourceTypes)}</b></div>
          </div>
        </header>
        <div className="source-mobile-accordions">
          <details className="source-mobile-accordion" open onToggle={handleDetailsToggle}>
            <summary>
              <span>ROLLUP</span>
              <small>SOURCE FAMILY / RECORDS / ORGS</small>
            </summary>
            <div className="source-pane-scroll">
              {data.sources.rollup.map((row) => (
                <div className="source-rollup-row" key={row.id}>
                  <i style={{ "--source-color": row.color } as CSSProperties} />
                  <span>{row.label}</span>
                  <strong>{formatNumber(row.records)}</strong>
                </div>
              ))}
            </div>
          </details>
          <details className="source-mobile-accordion" onToggle={handleDetailsToggle}>
            <summary>
              <span>REGISTERED SOURCES</span>
              <small>SOURCE ORGANISATION / PUBLIC ROLE / RECORDS</small>
            </summary>
            <div className="source-registry-scroll">
              {data.sources.registry.map((row) => (
                <div className="source-registry-row" key={row.id}>
                  <span>
                    <b>{row.name}</b>
                    <small>{row.publicRole} / {row.displayType}</small>
                  </span>
                  <strong>{formatNumber(row.recordCount)}</strong>
                </div>
              ))}
            </div>
          </details>
        </div>
      </section>
    </div>
  );
}

function MobileAboutView({ data }: { data: MobileArchiveData }) {
  return (
    <div className="about-view mobile-about-view">
      <header className="mobile-about-heading">
        <span>ABOUT</span>
        <h1>About AusFigures</h1>
        <p>AusFigures is a source-grounded public-text archive for tracing how humanoid or humanoid-adjacent supernatural figures appear in Australian public sources.</p>
      </header>
      <section className="about-status-panel">
        <header className="about-status-head">
          <i aria-hidden="true" />
          <span>DATA STATUS / PUBLIC CORPUS</span>
        </header>
        <div className="about-status-grid">
          <div><span>PUBLIC RECORDS</span><b>{formatNumber(data.summary.recordCount)}</b></div>
          <div><span>MAPPED RECORDS</span><b>{formatNumber(data.summary.mappedRecordCount)}</b></div>
          <div><span>SOURCE ORGS</span><b>{formatNumber(data.summary.sourceCount)}</b></div>
        </div>
      </section>
      <section className="about-grid">
        <MobileAboutModule title="Scope">
          It records published accounts, apparition narratives, local legends, traditional and spirit-person narratives, retellings, and related public discourse as source-grounded public records.
        </MobileAboutModule>
        <MobileAboutModule title="Map Limits">
          Public source exists does not mean a supernatural claim is verified. Map markers are public display locations for records, not habitats, populations, or proof.
        </MobileAboutModule>
        <MobileAboutModule title="Source And Ethics">
          Indigenous-related records require careful handling of terminology, source voice, publicness, cultural sensitivity, and display mode. Restricted or private knowledge is outside the public archive scope.
        </MobileAboutModule>
      </section>
    </div>
  );
}

function MobileAboutModule({ title, children }: { title: string; children: ReactNode }) {
  const reducedMotion = useMobilePrefersReducedMotion();
  const handleDetailsToggle = useCallback((event: SyntheticEvent<HTMLDetailsElement>) => {
    animateMobileDetails(event.currentTarget, reducedMotion);
  }, [reducedMotion]);

  return (
    <details className="about-module about-accordion-module" open onToggle={handleDetailsToggle}>
      <summary className="about-module-head">
        <i aria-hidden="true" />
        <span>{title}</span>
      </summary>
      <p>{children}</p>
    </details>
  );
}

function animateMobileDetails(details: HTMLDetailsElement, reducedMotion: boolean) {
  if (!details.open || reducedMotion) {
    return;
  }

  const content = Array.from(details.children).filter((child) => child.tagName !== "SUMMARY");
  if (content.length === 0) {
    return;
  }

  const timeline = createTimeline({
    defaults: {
      ease: "outCubic",
      duration: 280,
      composition: "replace",
    },
  });
  timeline.add(content, { opacity: [0.7, 1], translateY: [6, 0], delay: stagger(24) }, 0);
}

function addMobileTimelineTargets(
  timeline: Timeline,
  targets: NodeListOf<Element> | Element[],
  params: Record<string, unknown>,
  position: number,
) {
  if (targets.length > 0) {
    timeline.add(targets, params, position);
  }
}

export function MobileArchiveControls({ view }: { view: MobileControlView }) {
  const [collapsed, setCollapsed] = useState(true);
  const controlsRef = useRef<HTMLDivElement | null>(null);
  const idleTimer = useRef<number | null>(null);
  const keyboardInteraction = useRef(false);

  const clearIdleTimer = useCallback(() => {
    if (idleTimer.current) {
      window.clearTimeout(idleTimer.current);
      idleTimer.current = null;
    }
  }, []);

  const scheduleCollapse = useCallback(() => {
    clearIdleTimer();
    idleTimer.current = window.setTimeout(() => {
      const activeElement = document.activeElement;
      const keyboardFocus = keyboardInteraction.current && activeElement && controlsRef.current?.contains(activeElement);
      if (keyboardFocus) {
        idleTimer.current = null;
        return;
      }
      setCollapsed(true);
    }, MOBILE_NAV_IDLE_MS);
  }, [clearIdleTimer]);

  const expandAndSchedule = useCallback(() => {
    setCollapsed(false);
    scheduleCollapse();
  }, [scheduleCollapse]);

  useEffect(() => {
    return clearIdleTimer;
  }, [clearIdleTimer, view]);

  const handleNavigate = useCallback(() => {
    clearIdleTimer();
    setCollapsed(true);
  }, [clearIdleTimer]);

  const handleFocusCapture = useCallback(() => {
    clearIdleTimer();
    setCollapsed(false);
  }, [clearIdleTimer]);

  const handleBlurCapture = useCallback((event: FocusEvent<HTMLDivElement>) => {
    const nextTarget = event.relatedTarget;
    if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
      return;
    }
    scheduleCollapse();
  }, [scheduleCollapse]);

  return (
    <div
      ref={controlsRef}
      className={collapsed ? "mobile-archive-controls is-collapsed" : "mobile-archive-controls"}
      aria-label="Mobile archive controls"
      onFocusCapture={handleFocusCapture}
      onBlurCapture={handleBlurCapture}
      onPointerDownCapture={() => {
        keyboardInteraction.current = false;
      }}
      onKeyDownCapture={() => {
        keyboardInteraction.current = true;
      }}
      onPointerEnter={() => {
        if (isFineHoverPointer()) {
          clearIdleTimer();
        }
      }}
      onPointerLeave={() => {
        if (isFineHoverPointer()) {
          scheduleCollapse();
        }
      }}
    >
      <button
        type="button"
        className="mobile-nav-collapse-toggle"
        aria-label="Open mobile navigation"
        aria-expanded={!collapsed}
        onClick={expandAndSchedule}
      >
        <b className="mobile-nav-pill-label" aria-hidden="true">NAV</b>
        <span>AusFigures navigation</span>
      </button>
      <div className="mobile-archive-expanded">
        <MobileThemeControl />
        <nav className="mobile-archive-nav" aria-label="Mobile archive navigation">
          <Link
            className={view === "about" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/about"
            aria-label="Open about"
            aria-current={view === "about" ? "page" : undefined}
            onClick={handleNavigate}
          >
            <MobileNavIcon name="about" />
            <span>About</span>
          </Link>
          <Link
            className={view === "source" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/source"
            aria-label="Open source"
            aria-current={view === "source" ? "page" : undefined}
            onClick={handleNavigate}
          >
            <MobileNavIcon name="source" />
            <span>Source</span>
          </Link>
          <Link
            className={view === "density" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/density"
            aria-label="Open density"
            aria-current={view === "density" ? "page" : undefined}
            onClick={handleNavigate}
          >
            <MobileNavIcon name="density" />
            <span>Density</span>
          </Link>
          <Link
            className={view === "map" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/map"
            aria-label="Open map"
            aria-current={view === "map" ? "page" : undefined}
            onClick={handleNavigate}
          >
            <MobileNavIcon name="map" />
            <span>Map</span>
          </Link>
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
  const [theme, setTheme] = useState<DisplayTheme>(() => readStoredTheme());
  const [hydrated, setHydrated] = useState(false);

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

  return (
    <button
      type="button"
      className="mobile-archive-link mobile-theme-button"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      aria-pressed={theme === "light"}
      onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
    >
      <MobileNavIcon name="theme" theme={theme} />
      <span>{theme === "dark" ? "Dark mode" : "Light mode"}</span>
    </button>
  );
}

function MobileNavIcon({ name, theme }: { name: MobileNavName; theme?: DisplayTheme }) {
  if (name === "theme") {
    if (theme === "dark") {
      return (
        <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="12" r="4.4" />
          <path d="M12 3.6v2" />
          <path d="M12 18.4v2" />
          <path d="M3.6 12h2" />
          <path d="M18.4 12h2" />
          <path d="m6.1 6.1 1.4 1.4" />
          <path d="m16.5 16.5 1.4 1.4" />
          <path d="m17.9 6.1-1.4 1.4" />
          <path d="m7.5 16.5-1.4 1.4" />
        </svg>
      );
    }

    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M18.7 15.3A7.2 7.2 0 0 1 8.7 5.3 7.5 7.5 0 1 0 18.7 15.3Z" />
      </svg>
    );
  }

  if (name === "about") {
    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M8.4 18.2 12 6.4l3.6 11.8" />
        <path d="M9.7 14.2h4.6" />
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
