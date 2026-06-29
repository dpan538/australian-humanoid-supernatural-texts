"use client";

import type { CSSProperties, ReactNode } from "react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import mobileArchiveData from "@/public/data/mobile-archive.json";
import { MAP_VIEWBOX, STATE_SHAPES } from "@/lib/au-map-data";

type MobileControlView = "about" | "map" | "density" | "dashboard" | "source";
type DisplayTheme = "dark" | "light";
type MobileNavName = "theme" | "about" | "source" | "density" | "map";
const MOBILE_ARCHIVE_QUERY = "(max-width: 980px), (pointer: coarse)";
const MOBILE_NAV_IDLE_MS = 4600;
const THEME_STORAGE_KEY = "aus-archive-theme";
const MOBILE_DATA = mobileArchiveData as MobileArchiveData;
const MOBILE_MAP_VIEWBOX = { x: 24, y: 18, width: 930, height: 682 } as const;

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

function isMobileArchiveViewport() {
  return typeof window !== "undefined" && window.matchMedia(MOBILE_ARCHIVE_QUERY).matches;
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

export function MobileArchiveRoute({ view }: { view: MobileControlView }) {
  const routeView: MobileRouteView = view === "dashboard" ? "map" : view;

  return (
    <main className={`terminal-shell mobile-archive-shell mobile-view-${routeView}`}>
      <div className="noise-layer" aria-hidden="true" />
      <section className="mobile-archive-page" aria-label={`AusFigures ${routeView} mobile view`}>
        {routeView === "map" ? <MobileMapView /> : null}
        {routeView === "density" ? <MobileDensityView /> : null}
        {routeView === "source" ? <MobileSourceView /> : null}
        {routeView === "about" ? <MobileAboutView /> : null}
      </section>
      <MobileArchiveControls view={routeView} />
    </main>
  );
}

function MobileMapView() {
  const [hoverState, setHoverState] = useState<string | null>(null);
  const stateCounts = MOBILE_DATA.map.stateCounts;
  const stateCountMap = new Map(stateCounts.map((row) => [row.code, row.count]));
  const activeState = hoverState ? STATE_NAMES[hoverState] ?? hoverState : "Australia";
  const activeCount = hoverState ? stateCountMap.get(hoverState) ?? 0 : MOBILE_DATA.summary.mappedRecordCount;

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
          aria-label="Public record display locations across Australia"
        >
          {STATE_SHAPES.map((state) => {
            const count = stateCountMap.get(state.code) ?? 0;
            const intensity = count > 100 ? "hot" : count > 0 ? "warm" : "cold";
            return (
              <path
                key={state.code}
                className={`state-shape ${hoverState === state.code ? "hovered" : ""} ${intensity}`}
                d={state.d}
                onPointerEnter={() => setHoverState(state.code)}
                onPointerLeave={() => setHoverState(null)}
              />
            );
          })}
          <path className="coast-outline" d={STATE_SHAPES.map((state) => state.d).join(" ")} />
          <g className={`record-flag-layer ${hoverState ? "has-state-hover" : ""}`} aria-label="Mapped public record locations">
            {MOBILE_DATA.map.flags.map((flag) => (
              <MobileMapFlagMarker key={flag.id} flag={flag} stateLinked={hoverState === flag.state} />
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
      <p className="mobile-map-note">{MOBILE_DATA.map.interpretation}</p>
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
              className={hoverState === row.code ? "state-mini active" : "state-mini"}
              key={row.code}
              onPointerEnter={() => setHoverState(row.code)}
              onPointerLeave={() => setHoverState(null)}
              onFocus={() => setHoverState(row.code)}
              onBlur={() => setHoverState(null)}
            >
              <span>{row.code}</span>
              <b>{formatNumber(row.count)}</b>
            </button>
          ))}
        </div>
        <div className="map-health-note">
          <span>MAPPED RECORDS</span>
          <b>{formatNumber(MOBILE_DATA.summary.mappedRecordCount)}</b>
          <small>{formatNumber(MOBILE_DATA.summary.mappedRecordCount)} mapped / {formatNumber(MOBILE_DATA.summary.recordCount)} public records</small>
          <em>one display marker per mapped public record</em>
        </div>
      </aside>
    </div>
  );
}

function MobileMapFlagMarker({ flag, stateLinked }: { flag: MobileMapFlag; stateLinked: boolean }) {
  const className = ["record-flag", "precise", flag.toneClass, stateLinked ? "state-linked" : ""].filter(Boolean).join(" ");

  return (
    <g className={className} aria-label={`${flag.title ?? "Public record"} ${flag.state}`}>
      <circle className="record-flag-dot" cx={flag.displayX} cy={flag.displayY} r={stateLinked ? 4.1 : 3.25} />
    </g>
  );
}

function MobileDensityView() {
  return (
    <div className="density-view mobile-density-view">
      <header className="density-header">
        <div>
          <span>TIME DENSITY</span>
          <p>Density shows public-text record distribution and source coverage. It is not a claim about real-world frequency.</p>
        </div>
        <b>
          {MOBILE_DATA.summary.earliestYear}-{MOBILE_DATA.summary.latestYear} / {formatNumber(MOBILE_DATA.summary.recordCount)} PUBLIC RECORDS / {formatNumber(MOBILE_DATA.summary.mappedRecordCount)} MAPPED
        </b>
      </header>
      <div className="density-bands">
        {MOBILE_DATA.density.periods.map((period) => (
          <MobileDensityBand key={period.id} period={period} />
        ))}
      </div>
      <article className="density-chart-card mobile-density-trend">
        <header>
          <span>ANNUAL TREND</span>
          <b>Dated public records by year</b>
        </header>
        <MobileAnnualSparkline />
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

function MobileAnnualSparkline() {
  const series = MOBILE_DATA.density.annualSeries;
  const width = 340;
  const height = 112;
  const max = Math.max(1, ...series.map((row) => row.count));
  const minYear = Math.min(...series.map((row) => row.year));
  const maxYear = Math.max(...series.map((row) => row.year));
  const points = series.map((row) => {
    const x = ((row.year - minYear) / Math.max(1, maxYear - minYear)) * (width - 24) + 12;
    const y = height - 14 - (row.count / max) * (height - 28);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <svg className="density-line-chart mobile-sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Annual public record trend">
      <line className="density-chart-grid" x1="12" x2={width - 12} y1={height - 14} y2={height - 14} />
      <polyline className="density-line-public density-chart-path" points={points} fill="none" />
      <text className="density-chart-axis" x="12" y={height - 2}>{minYear}</text>
      <text className="density-chart-axis" x={width - 12} y={height - 2} textAnchor="end">{maxYear}</text>
    </svg>
  );
}

function MobileSourceView() {
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
            <div className="source-metric-cell"><span>SOURCE ORGS</span><b>{formatNumber(MOBILE_DATA.sources.metrics.sourceOrgs)}</b></div>
            <div className="source-metric-cell"><span>PUBLIC RECORDS</span><b>{formatNumber(MOBILE_DATA.sources.metrics.publicRecords)}</b></div>
            <div className="source-metric-cell"><span>SOURCE TYPES</span><b>{formatNumber(MOBILE_DATA.sources.metrics.sourceTypes)}</b></div>
          </div>
        </header>
        <div className="source-mobile-accordions">
          <details className="source-mobile-accordion" open>
            <summary>
              <span>ROLLUP</span>
              <small>SOURCE FAMILY / RECORDS / ORGS</small>
            </summary>
            <div className="source-pane-scroll">
              {MOBILE_DATA.sources.rollup.map((row) => (
                <div className="source-rollup-row" key={row.id}>
                  <i style={{ "--source-color": row.color } as CSSProperties} />
                  <span>{row.label}</span>
                  <strong>{formatNumber(row.records)}</strong>
                </div>
              ))}
            </div>
          </details>
          <details className="source-mobile-accordion">
            <summary>
              <span>REGISTERED SOURCES</span>
              <small>SOURCE ORGANISATION / PUBLIC ROLE / RECORDS</small>
            </summary>
            <div className="source-registry-scroll">
              {MOBILE_DATA.sources.registry.map((row) => (
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

function MobileAboutView() {
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
          <div><span>PUBLIC RECORDS</span><b>{formatNumber(MOBILE_DATA.summary.recordCount)}</b></div>
          <div><span>MAPPED RECORDS</span><b>{formatNumber(MOBILE_DATA.summary.mappedRecordCount)}</b></div>
          <div><span>SOURCE ORGS</span><b>{formatNumber(MOBILE_DATA.summary.sourceCount)}</b></div>
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
  return (
    <details className="about-module about-accordion-module" open>
      <summary className="about-module-head">
        <i aria-hidden="true" />
        <span>{title}</span>
      </summary>
      <p>{children}</p>
    </details>
  );
}

export function MobileArchiveControls({ view }: { view: MobileControlView }) {
  const [collapsed, setCollapsed] = useState(false);
  const idleTimer = useRef<number | null>(null);

  const clearIdleTimer = useCallback(() => {
    if (idleTimer.current) {
      window.clearTimeout(idleTimer.current);
      idleTimer.current = null;
    }
  }, []);

  const scheduleCollapse = useCallback(() => {
    clearIdleTimer();
    idleTimer.current = window.setTimeout(() => setCollapsed(true), MOBILE_NAV_IDLE_MS);
  }, [clearIdleTimer]);

  const expandAndSchedule = useCallback(() => {
    setCollapsed(false);
    scheduleCollapse();
  }, [scheduleCollapse]);

  useEffect(() => {
    expandAndSchedule();
    return clearIdleTimer;
  }, [clearIdleTimer, expandAndSchedule, view]);

  return (
    <div
      className={collapsed ? "mobile-archive-controls is-collapsed" : "mobile-archive-controls"}
      aria-label="Mobile archive controls"
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
          >
            <MobileNavIcon name="about" />
            <span>About</span>
          </Link>
          <Link
            className={view === "source" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/source"
            aria-label="Open source"
            aria-current={view === "source" ? "page" : undefined}
          >
            <MobileNavIcon name="source" />
            <span>Source</span>
          </Link>
          <Link
            className={view === "density" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/density"
            aria-label="Open density"
            aria-current={view === "density" ? "page" : undefined}
          >
            <MobileNavIcon name="density" />
            <span>Density</span>
          </Link>
          <Link
            className={view === "map" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/map"
            aria-label="Open map"
            aria-current={view === "map" ? "page" : undefined}
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

  useEffect(() => {
    setTheme(readStoredTheme());
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
      aria-label={`Theme ${theme}; toggle dark and light mode`}
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
