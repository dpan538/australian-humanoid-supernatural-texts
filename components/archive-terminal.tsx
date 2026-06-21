"use client";

import { CSSProperties, useEffect, useState } from "react";
import Link from "next/link";
import type { DateBand, FrontendData, RecordItem } from "@/lib/types";
import { MAP_BOUNDARY_SOURCE, MAP_VIEWBOX, STATE_SHAPES, TERRAIN_TILES } from "@/lib/au-map-data";

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

function numberFormat(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "--";
  }
  return new Intl.NumberFormat("en-AU").format(value);
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

function entriesDescending(values: Record<string, number>, limit?: number) {
  const entries = Object.entries(values).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return limit ? entries.slice(0, limit) : entries;
}

function conicGradient(values: Record<string, number>) {
  const palette = ["#f2f2ed", "#a7ff63", "#8ed8ff", "#d7d0c6", "#7f858a", "#5f9361", "#b0b7bc", "#2f3031"];
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

export function ArchiveTerminal({ data, view }: { data: FrontendData; view: ViewMode }) {
  const nextView = getNextView(view);
  const [selectedRecord, setSelectedRecord] = useState<RecordItem | null>(null);
  const overlayNavigation = selectedRecord ? recordNavigationContext(data, selectedRecord) : null;

  function showAdjacentRecord(direction: 1 | -1) {
    if (!overlayNavigation || overlayNavigation.records.length < 2) {
      return;
    }
    const nextIndex =
      (overlayNavigation.currentIndex + direction + overlayNavigation.records.length) % overlayNavigation.records.length;
    setSelectedRecord(overlayNavigation.records[nextIndex]);
  }

  useEffect(() => {
    if (!selectedRecord) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSelectedRecord(null);
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
  }, [selectedRecord, overlayNavigation]);

  return (
    <main className="terminal-shell">
      <div className="noise-layer" aria-hidden="true" />
      <div className="terminal-stage">
        <section className={`view-area view-area-${view}`} aria-label={`${view} data view`}>
          {view === "map" ? <MapView data={data} onSelectRecord={setSelectedRecord} /> : null}
          {view === "density" ? <DensityView data={data} onSelectRecord={setSelectedRecord} /> : null}
          {view === "dashboard" ? <DashboardView data={data} onSelectRecord={setSelectedRecord} /> : null}
          {view === "source" ? <SourceView data={data} /> : null}
        </section>

        <div className="external-control-dock" aria-label="Fixed external controls">
          <Link className="dock-button about-button" href="/about">
            About
          </Link>
          <Link className={view === "source" ? "dock-button source-button active" : "dock-button source-button"} href="/source" aria-current={view === "source" ? "page" : undefined}>
            Source
          </Link>
          <Link
            className="dock-button view-cycle-button"
            href={VIEW_PATHS[nextView]}
            aria-label={`Current view ${VIEW_LABELS[view]}; switch to ${VIEW_LABELS[nextView]}`}
            title={`Switch to ${VIEW_LABELS[nextView]}`}
          >
            <span className="view-label-current">{VIEW_LABELS[view]}</span>
            <span className="view-label-next">{VIEW_LABELS[nextView]}</span>
          </Link>
        </div>
      </div>
      {selectedRecord ? (
        <RecordCardOverlay
          record={selectedRecord}
          navigation={overlayNavigation}
          onClose={() => setSelectedRecord(null)}
          onNavigate={showAdjacentRecord}
        />
      ) : null}
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

function MapView({ data, onSelectRecord }: { data: FrontendData; onSelectRecord: (record: RecordItem) => void }) {
  const [hoverState, setHoverState] = useState<string | null>(null);
  const [hoverRecord, setHoverRecord] = useState<RecordItem | null>(null);
  const stateCounts = data.summary.corpus_state_counts ?? data.summary.state_record_counts;
  const mapRecords = data.records.filter(
    (record) => record.has_strict_map_point && record.map_latitude !== null && record.map_longitude !== null,
  );
  const preciseStateCounts = mapRecords.reduce<Record<string, number>>((acc, record) => {
    if (record.state_territory) {
      acc[record.state_territory] = (acc[record.state_territory] ?? 0) + 1;
    }
    return acc;
  }, {});
  const activeState = hoverState ? STATE_NAMES[hoverState] : "Australia";
  const activeCount = hoverState ? preciseStateCounts[hoverState] ?? 0 : mapRecords.length;

  return (
    <div className="map-view">
      <div className="map-source-block" aria-label="Map boundary and terrain source">
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
          <g className={`record-flag-layer ${hoverRecord ? "has-hover" : ""}`} aria-label="Strict geocoded public record flags">
            {mapRecords.map((record, index) => {
              const projected = projectPoint(record.map_latitude as number, record.map_longitude as number);
              const x = svgCoord(projected.x);
              const y = svgCoord(projected.y);
              const flagDelay = mapRecords.length > 1 ? (index / Math.max(1, mapRecords.length - 1)) * 820 : 0;
              const selected = hoverRecord?.record_id === record.record_id;
              const stateLinked = hoverState === record.state_territory;
              const toneClass = mapSourceTone(record).className;
              const className = ["record-flag", "precise", toneClass, selected ? "active" : "", stateLinked ? "state-linked" : ""]
                .filter(Boolean)
                .join(" ");
              return (
                <g
                  key={`${record.record_id}-${record.map_place_name ?? "strict"}-${index}`}
                  className={className}
                  style={{ "--flag-delay": `${flagDelay.toFixed(1)}ms` } as CSSProperties}
                  onMouseEnter={() => {
                    setHoverRecord(record);
                    setHoverState(record.state_territory ?? null);
                  }}
                  onMouseLeave={() => {
                    setHoverRecord(null);
                    setHoverState(null);
                  }}
                  onFocus={() => {
                    setHoverRecord(record);
                    setHoverState(record.state_territory ?? null);
                  }}
                  onBlur={() => {
                    setHoverRecord(null);
                    setHoverState(null);
                  }}
                  onClick={() => {
                    onSelectRecord(record);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectRecord(record);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Open strict geocoded record ${record.title ?? record.map_place_name}`}
                >
                  <circle className="record-flag-hit" cx={x} cy={y} r="10" />
                  <circle className="record-flag-dot" cx={x} cy={y} r={selected ? 5.2 : stateLinked ? 3.9 : 3.25} />
                  {selected ? (
                    <text className="record-flag-label" x={Math.min(x + 12, MAP_VIEWBOX.width - 150)} y={Math.max(y - 10, 26)}>
                      {record.year ?? "--"} / {truncate(record.canonical_figure_guess ?? record.canonical_figure ?? record.title, 24)}
                    </text>
                  ) : null}
                </g>
              );
            })}
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
          <span className="tiny-label">REGION</span>
          <strong>{activeState}</strong>
          <span className="readout-number">{numberFormat(activeCount)}</span>
          <span className="readout-tail">records</span>
        </div>
        <div className="readout-grid">
          {Object.entries(STATE_NAMES).map(([code]) => (
            <div
              className={hoverState === code ? "state-mini active" : "state-mini"}
              key={code}
              onMouseEnter={() => setHoverState(code)}
              onPointerEnter={() => setHoverState(code)}
              onMouseLeave={() => setHoverState(null)}
              onPointerLeave={() => setHoverState(null)}
              onFocus={() => setHoverState(code)}
              onBlur={() => setHoverState(null)}
              tabIndex={0}
            >
              <span>{code}</span>
              <b>{preciseStateCounts[code] ?? 0}</b>
            </div>
          ))}
        </div>
        <div className="map-health-note">
          <span>STRICT GEO</span>
          <b>{mapRecords.length}</b>
          <small>verified map points / {data.summary.record_count} records</small>
        </div>
      </aside>
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

function DensityView({ data, onSelectRecord }: { data: FrontendData; onSelectRecord: (record: RecordItem) => void }) {
  const maxRecords = Math.max(...data.date_bands.map((band) => band.record_count), 1);
  const maxQueries = Math.max(...data.date_bands.map((band) => band.planned_query_count), 1);
  const queryTypes = data.queries.reduce<Record<string, number>>((acc, query) => {
    acc[query.query_type] = (acc[query.query_type] ?? 0) + 1;
    return acc;
  }, {});
  const locationHealth = {
    strict_geo: data.summary.precise_point_count,
    broad_or_review: Math.max(0, data.summary.record_count - data.summary.precise_point_count),
    locations_total: data.summary.location_count,
  };

  return (
    <div className="density-view">
      <header className="density-header">
        <span>TIME DENSITY / NONLINEAR BANDS</span>
        <b>
          {data.summary.earliest_year}-{data.summary.latest_year} / {data.summary.precise_point_count} GEO
        </b>
      </header>
      <div className="density-bands">
        {data.date_bands.map((band, index) => (
          <DensityBand
            key={band.id}
            band={band}
            index={index}
            maxRecords={maxRecords}
            maxQueries={maxQueries}
            records={data.records}
            onSelectRecord={onSelectRecord}
          />
        ))}
      </div>
      <div className="density-aux-grid">
        <DensitySignal title="SOURCE FIELD" values={data.summary.source_type_counts} />
        <DensitySignal title="LOCATION HEALTH" values={locationHealth} />
        <DensityFigureRail records={data.records} onSelectRecord={onSelectRecord} />
      </div>
      <div className="density-footer">
        <div className="density-note">
          <span>QUERY TYPES</span>
          <b>{entriesDescending(queryTypes, 3).map(([label, value]) => `${truncate(label, 12)} ${value}`).join(" / ")}</b>
        </div>
      </div>
    </div>
  );
}

function DensityBand({
  band,
  index,
  maxRecords,
  maxQueries,
  records,
  onSelectRecord,
}: {
  band: DateBand;
  index: number;
  maxRecords: number;
  maxQueries: number;
  records: RecordItem[];
  onSelectRecord: (record: RecordItem) => void;
}) {
  const recordLevel = Math.ceil((band.record_count / maxRecords) * 28);
  const queryLevel = Math.ceil((band.planned_query_count / maxQueries) * 28);
  const char = DENSITY_CHARS[Math.min(DENSITY_CHARS.length - 1, index)];
  const firstRecord = records.find((record) => record.date_band === band.id);
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
      <div className="density-matrix" aria-hidden="true">
        {Array.from({ length: 28 }).map((_, cellIndex) => (
          <span key={cellIndex} className={cellIndex < recordLevel ? "matrix-cell lit" : "matrix-cell"}>
            {cellIndex < recordLevel ? char : "."}
          </span>
        ))}
      </div>
      <div className="band-meta">
        <span>{band.label}</span>
        <b>{numberFormat(band.record_count)}</b>
        <small style={{ "--query-level": `${Math.max(6, queryLevel * 3)}%` } as CSSProperties}>Q {band.planned_query_count}</small>
      </div>
    </section>
  );
}

function DensitySignal({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = entriesDescending(values, 5);
  const max = Math.max(...entries.map(([, value]) => value), 1);

  return (
    <section className="density-signal">
      <span className="tiny-label">{title}</span>
      <div className="density-signal-bars">
        {entries.map(([label, value]) => (
          <div key={label} className="density-signal-row">
            <span>{truncate(label, 18)}</span>
            <i style={{ "--signal-width": `${Math.max(8, (value / max) * 100)}%` } as CSSProperties} />
            <b>{value}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function DensityFigureRail({
  records,
  onSelectRecord,
}: {
  records: RecordItem[];
  onSelectRecord: (record: RecordItem) => void;
}) {
  const figures = records.reduce<Record<string, number>>((acc, record) => {
    const key = record.canonical_figure_guess || record.canonical_figure || "uncoded";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
  const entries = entriesDescending(figures, 8);

  return (
    <section className="density-figure-rail">
      <span className="tiny-label">FIGURE SIGNAL</span>
      <div>
        {entries.map(([figure, value], index) => (
          <button
            key={figure}
            type="button"
            className={index % 3 === 0 ? "rail-mark strong" : "rail-mark"}
            onClick={() => {
              const record = records.find((item) => (item.canonical_figure_guess || item.canonical_figure || "uncoded") === figure);
              if (record) {
                onSelectRecord(record);
              }
            }}
          >
            {truncate(figure, 10)}:{value}
          </button>
        ))}
      </div>
    </section>
  );
}

function DashboardView({ data, onSelectRecord }: { data: FrontendData; onSelectRecord: (record: RecordItem) => void }) {
  return (
    <div className="dashboard-view">
      <DashboardTrackNetwork data={data} onSelectRecord={onSelectRecord} />
      <DashboardControlConsole data={data} />
    </div>
  );
}

function DashboardTrackNetwork({
  data,
  onSelectRecord,
}: {
  data: FrontendData;
  onSelectRecord: (record: RecordItem) => void;
}) {
  const tracks = dashboardTrackSample(data);
  const nodes = tracks.map((record, index) => ({
    record,
    x: index % 3 === 0 ? 58 : index % 3 === 1 ? 174 : 274,
    y: 74 + index * 27,
    tx: 446,
    ty: 132 + index * 23,
  }));

  return (
    <section className="dashboard-track-network dash-hover-zone" aria-label="Record network and track list">
      <svg className="network-svg" viewBox="0 0 760 520" role="img" aria-label="Archive record signal network">
        <path className="corner-mark top-left" d="M136 28 h-18 v18 M136 28 v-24" />
        <path className="corner-mark top-right" d="M596 28 h18 v18 M596 28 v-24" />
        <path className="corner-mark bottom-left" d="M136 492 h-18 v-18 M136 492 v24" />
        <path className="corner-mark bottom-right" d="M596 492 h18 v-18 M596 492 v24" />
        <rect className="network-wave-box" x="250" y="70" width="146" height="132" />
        {["0A", "0B", "0C", "0D", "0E"].map((pass, passIndex) => (
          <g key={pass} transform={`translate(262 ${84 + passIndex * 23})`}>
            <text className="network-micro-text" x="0" y="8">
              PASS/{pass}
            </text>
            {Array.from({ length: 42 }).map((_, barIndex) => {
              const source = tracks[(barIndex + passIndex) % Math.max(tracks.length, 1)];
              const height = 2 + (((source?.year ?? 1800) + barIndex * 7) % 17);
              return <rect key={barIndex} className="network-wave-bar" x={50 + barIndex * 2.1} y={18 - height} width="1.1" height={height} />;
            })}
          </g>
        ))}
        <rect className="network-average" x="220" y="248" width="186" height="56" />
        <text className="network-micro-text" x="228" y="266">
          AVERAGE
        </text>
        <text className="network-micro-text" x="228" y="292">
          TOTAL TIME: {data.summary.earliest_year}-{data.summary.latest_year}
        </text>
        {nodes.map((node, index) => (
          <g key={`line-${node.record.record_id}`}>
            <line className="network-wire" x1={node.x + 32} y1={node.y + 8} x2={318} y2={276} />
            <line className="network-wire pale" x1={318} y1={276} x2={node.tx - 16} y2={node.ty} />
            {index % 4 === 0 ? <line className="network-wire long" x1={node.x + 20} y1={node.y + 8} x2={48 + index * 8} y2={438 - index * 11} /> : null}
          </g>
        ))}
        {nodes.map((node) => (
          <g
            key={node.record.record_id}
            className="network-record-target"
            onClick={() => onSelectRecord(node.record)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectRecord(node.record);
              }
            }}
            role="button"
            tabIndex={0}
            aria-label={`Open record ${node.record.title ?? node.record.record_id}`}
          >
            <rect className="network-slot" x={node.x} y={node.y} width="52" height="15" />
            <rect className="network-slot-fill" x={node.x + 8} y={node.y + 4} width="33" height="7" />
            <circle className="network-dot" cx={node.x - 8} cy={node.y + 8} r="3" />
            <text className="network-slot-label" x={node.x + 58} y={node.y + 11}>
              SLOT_{String(node.record.record_id).padStart(2, "0")}
            </text>
          </g>
        ))}
        <circle className="network-big-dot" cx="382" cy="448" r="8" />
        <rect className="network-bottom-mark" x="402" y="443" width="9" height="9" />
        <rect className="network-bottom-mark" x="548" y="446" width="7" height="7" />
      </svg>
      <div className="track-list">
        <span>TRACKS</span>
        {tracks.map((record, index) => (
          <button className="track-row" key={record.record_id} type="button" onClick={() => onSelectRecord(record)}>
            <b>{String(index + 1).padStart(2, "0")}.</b>
            <i>{dashboardTrackLabel(record)}</i>
          </button>
        ))}
      </div>
      <div className="network-footer">
        <span>PUBLIC DATA FIELD</span>
        <span>{data.summary.record_count} RECORDS</span>
        <span>{data.summary.query_count} QUERIES</span>
      </div>
    </section>
  );
}

function DashboardControlConsole({ data }: { data: FrontendData }) {
  const [mode, setMode] = useState<"records" | "locations" | "queries">("queries");
  const queryTypes = data.queries.reduce<Record<string, number>>((acc, query) => {
    acc[query.query_type] = (acc[query.query_type] ?? 0) + 1;
    return acc;
  }, {});
  const stateCounts = data.summary.corpus_state_counts ?? data.summary.state_record_counts;
  const strictStateCounts =
    data.summary.strict_state_counts ??
    data.records.reduce<Record<string, number>>((acc, record) => {
      if (record.has_strict_map_point && record.state_territory) {
        acc[record.state_territory] = (acc[record.state_territory] ?? 0) + 1;
      }
      return acc;
    }, {});
  const figureCounts = data.records.reduce<Record<string, number>>((acc, record) => {
    const label = record.canonical_figure_guess || record.canonical_figure || "uncoded";
    acc[label] = (acc[label] ?? 0) + 1;
    return acc;
  }, {});
  const sourceRows = Object.entries(data.summary.source_rollup)
    .sort((a, b) => b[1].query_count - a[1].query_count || b[1].record_count - a[1].record_count)
    .slice(0, 6);
  const activeValues =
    mode === "records" ? figureCounts : mode === "locations" ? strictStateCounts : queryTypes;
  const activeTabs = [
    { id: "records" as const, label: "RECORDS" },
    { id: "locations" as const, label: "GEO FIELD" },
    { id: "queries" as const, label: "QUERY FIELD" },
  ];
  const topMetrics =
    mode === "records"
      ? [
          ["CARD READY", data.summary.record_count],
          ["FIGURES", data.summary.figure_count],
        ]
      : mode === "locations"
        ? [
            ["STRICT", data.summary.precise_point_count],
            ["BROAD", data.summary.broad_location_count],
          ]
        : [
            ["QUERIES", data.summary.query_count],
            ["EXACT", queryTypes.exact_phrase ?? 0],
          ];
  const outputValues = [
    { id: "records" as const, value: data.summary.record_count, label: "Card-ready records" },
    { id: "locations" as const, value: data.summary.precise_point_count, label: "Strict geocoded map points" },
    { id: "queries" as const, value: data.summary.query_count, label: "Planned queries" },
  ];
  const stateOrder = ["WA", "NT", "SA", "QLD", "NSW", "VIC", "TAS", "ACT"];
  const stateEntries = stateOrder.map((state) => [state, mode === "locations" ? strictStateCounts[state] ?? 0 : stateCounts[state] ?? 0] as const);
  const maxStateCount = Math.max(...stateEntries.map(([, value]) => value), 1);

  return (
    <section className="dashboard-console dash-hover-zone" aria-label="Database control console">
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

      <div className="console-grid-top">
        <MiniControl label={topMetrics[0][0] as string} value={topMetrics[0][1] as number} />
        <MiniControl label={topMetrics[1][0] as string} value={topMetrics[1][1] as number} />
        <ConsoleWave records={data.records} />
      </div>

      <div className="console-sequencer">
        <span className="tiny-label">TIME CUTTER</span>
        <div>
          {data.date_bands.map((band, index) => (
            <span key={band.id} className={band.record_count > 0 ? "lit" : ""}>
              {index + 1}
            </span>
          ))}
        </div>
      </div>

      <div className="console-effect-grid">
        {entriesDescending(activeValues, 8).map(([label, value]) => (
          <span key={label}>
            {truncate(label, 14)} <b>{value}</b>
          </span>
        ))}
      </div>

      <div className="console-mid-row">
        <SourceWheel values={data.summary.source_type_counts} />
        <ConsolePolyline values={data.summary.records_by_year} />
      </div>

      <div className="console-source-grid">
        {sourceRows.map(([label, counts]) => (
          <div key={label}>
            <span>{truncate(label, 15)}</span>
            <i style={{ "--source-meter": `${Math.max(8, Math.min(100, counts.query_count))}%` } as CSSProperties} />
          </div>
        ))}
      </div>

      <div className="console-lollipops">
        {stateEntries.map(([state, value]) => (
          <span
            key={state}
            style={{ "--stem": `${Math.round(22 + (value / maxStateCount) * 58)}px` } as CSSProperties}
            aria-label={`${state}: ${value} records`}
          >
            <b>{state}</b>
            <em>{value}</em>
          </span>
        ))}
      </div>
    </section>
  );
}

function MiniControl({ label, value }: { label: string; value: number }) {
  return (
    <div className="mini-control">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function ConsoleWave({ records }: { records: RecordItem[] }) {
  const points = records.slice(0, 16).map((record, index) => {
    const x = 6 + index * 12;
    const y = 38 - (((record.year ?? 1842) % 29) / 29) * 30;
    return `${x},${y.toFixed(1)}`;
  });

  return (
    <svg className="console-wave" viewBox="0 0 200 48" role="img" aria-label="Record waveform">
      <polyline points={points.join(" ")} />
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

  return (
    <div className="source-wheel-module">
      <span className="tiny-label">SOURCE</span>
      <div className="source-wheel" style={{ "--source-wheel": conicGradient(values) } as CSSProperties}>
        <i />
      </div>
      <div className="source-wheel-list">
        {entries.map(([label, value]) => (
          <span key={label}>
            <b style={{ "--source-dot": `${Math.max(22, (value / max) * 100)}%` } as CSSProperties} />
            {truncate(label, 12)}
          </span>
        ))}
      </div>
    </div>
  );
}

function ConsolePolyline({ values }: { values: Record<string, number> }) {
  const rawEntries = Object.entries(values)
    .map(([year, value]) => [Number(year), value] as const)
    .filter(([year]) => Number.isFinite(year))
    .sort(([a], [b]) => a - b);
  const entries = aggregateYearValues(rawEntries, 28);
  const max = Math.max(...entries.map(([, value]) => value), 1);
  const xFor = (index: number) => (entries.length <= 1 ? 110 : 10 + (index / (entries.length - 1)) * 200);
  const yFor = (value: number) => 70 - (value / max) * 52;
  const points = entries.map(([, value], index) => `${xFor(index).toFixed(1)},${yFor(value).toFixed(1)}`).join(" ");

  return (
    <svg className="console-polyline" viewBox="0 0 220 82" role="img" aria-label="Year counts polyline">
      {entries.map(([label, value], index) => (
        <rect
          key={`bar-${label}`}
          className="console-density-bar"
          x={xFor(index) - 2.8}
          y={yFor(value)}
          width="5.6"
          height={72 - yFor(value)}
        />
      ))}
      <polyline points={points} />
      {entries.map(([label, value], index) => (
        <circle key={label} cx={xFor(index)} cy={yFor(value)} r={Math.max(1.4, Math.min(2.6, 1.2 + value / max * 1.8))} />
      ))}
    </svg>
  );
}

function dashboardTrackLabel(record: RecordItem) {
  const year = record.year ? String(record.year) : "----";
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
  return `${truncate(label, 26)} (${year})`;
}

function dashboardTrackSample(data: FrontendData) {
  const pool = data.records.filter((record) => record.relevance_code !== "noise");
  const byYear = [...pool].sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999) || a.record_id - b.record_id);
  const selected: RecordItem[] = [];
  const seen = new Set<number>();
  const add = (record: RecordItem | undefined) => {
    if (record && !seen.has(record.record_id) && selected.length < 14) {
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
      if (keys.size >= limit || selected.length >= 14) {
        break;
      }
    }
  };

  const figureOf = (record: RecordItem) => record.canonical_figure_guess || record.canonical_figure || record.title || "uncoded";
  const nonDominant = byYear.filter((record) => !/^yowie$/i.test(figureOf(record)));
  for (const record of nonDominant) {
    add(record);
    if (selected.length >= 9) {
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

function recordBody(record: RecordItem) {
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

function recordNavigationContext(data: FrontendData, record: RecordItem): RecordNavigationContext {
  const state = record.has_strict_map_point ? record.state_territory : null;
  const strictPointRecords = data.records.filter(
    (item) => Boolean(state) && item.has_strict_map_point && item.state_territory === state,
  );
  const unique = strictPointRecords.sort((a, b) => {
    const yearA = a.year ?? 9999;
    const yearB = b.year ?? 9999;
    return yearA - yearB || (a.title ?? "").localeCompare(b.title ?? "") || a.record_id - b.record_id;
  });
  const fallback = [...data.records].sort((a, b) => {
    const yearA = a.year ?? 9999;
    const yearB = b.year ?? 9999;
    return yearA - yearB || (a.title ?? "").localeCompare(b.title ?? "") || a.record_id - b.record_id;
  });
  const records = unique.length ? unique : fallback;
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
  const location = record.location_summary || "location unverified";
  const sourceName = record.source_name || record.publication || "public source";
  const sourceClass = tone.className;
  const year = record.year ?? "----";
  const title = record.title || recordDisplayTitle(record);
  const body = recordBody(record);
  const canNavigate = Boolean(navigation && navigation.records.length > 1);
  const navPosition = navigation ? `${navigation.currentIndex + 1} / ${navigation.records.length}` : "1 / 1";

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
          aria-label={`Record ${title}`}
        >
        <section className="record-card-table" aria-label="Record metadata">
          <div className="record-card-table-top">
            <span>aus humanoid record</span>
            <span>{navigation?.regionLabel ?? "archive"} / {navPosition}</span>
            <button type="button" onClick={onClose} aria-label="Close record card">
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
          <h2>{recordDisplayTitle(record)}</h2>
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

function SourceView({ data }: { data: FrontendData }) {
  const sourceRows = Object.entries(data.summary.source_rollup).sort((a, b) => b[1].query_count - a[1].query_count);
  const ethicsRows = entriesDescending(data.summary.ethics_counts);
  return (
    <div className="source-view" aria-label="Sources">
      <div className="source-display">
        <header className="source-display-header">
          <span>SOURCE REGISTER</span>
          <h2>PUBLIC SOURCE FIELD</h2>
          <div>
            <b>{data.summary.source_count}</b>
            <b>{data.summary.record_count}</b>
            <b>{data.summary.query_count}</b>
          </div>
        </header>

        <div className="source-display-grid">
          <div className="source-display-column">
            <section className="source-display-section source-rollup-section" aria-label="Source rollup">
              <div className="source-section-kicker">ROLLUP</div>
              {sourceRows.map(([sourceType, counts]) => (
                <div className="source-display-row" key={sourceType}>
                  <span>{sourceType}</span>
                  <b>R {counts.record_count}</b>
                  <b>Q {counts.query_count}</b>
                </div>
              ))}
            </section>

            <section className="source-display-section source-ethics-section" aria-label="Ethics flags">
              <div className="source-section-kicker">ETHICS FLAG</div>
              {ethicsRows.map(([label, count]) => (
                <div className="source-display-row" key={label}>
                  <span>{label}</span>
                  <b>{count}</b>
                </div>
              ))}
            </section>

            <section className="source-display-section source-repo-section" aria-label="Repository">
              <div className="source-section-kicker">REPOSITORY</div>
              <a href="https://github.com/dpan538/australian-humanoid-supernatural-texts" target="_blank" rel="noreferrer">
                GITHUB / DPAN538
                <span>AUSTRALIAN-HUMANOID-SUPERNATURAL-TEXTS</span>
              </a>
            </section>
          </div>

          <section className="source-display-section source-register-section" aria-label="Registered sources">
            <div className="source-section-kicker">REGISTERED SOURCES</div>
            <div className="source-register-scroll">
              {data.sources.map((source) => (
                <div className="source-display-row source-register-row" key={source.source_id}>
                  <span>{source.source_name}</span>
                  <div>
                    <b>{source.source_type}</b>
                    <b>{source.publicness_level}</b>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <p className="source-display-note">{data.scope.ethical_note}</p>
      </div>
    </div>
  );
}
