"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, RefObject } from "react";
import type { FrontendData } from "@/lib/types";
import {
  buildSourceRegistryData,
  type SourceRegistryRow,
  type SourceRollupRow,
  type SourceTypeRollupRow,
} from "@/lib/source-view-data";
import { useSourcePaneResize } from "@/components/source/use-source-pane-resize";
import { useSourceTerminalMotion } from "@/components/source/use-source-terminal-motion";

const DEFAULT_VISIBLE_SOURCE_ROWS = 160;

export function SourceView({ data }: { data: FrontendData }) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [rootElement, setRootElement] = useState<HTMLDivElement | null>(null);
  const filterRef = useRef<HTMLInputElement | null>(null);
  const registryData = useMemo(() => buildSourceRegistryData(data), [data]);
  const [filter, setFilter] = useState("");
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(() => registryData.registryRows[0]?.source.source_id ?? null);
  const [mobilePane, setMobilePane] = useState<"rollup" | "registry">("registry");
  const { ratio, dragging, separatorProps } = useSourcePaneResize(rootRef);

  const filteredRows = useMemo(() => {
    const query = filter.trim().toLowerCase();
    const rows = query
      ? registryData.registryRows.filter((row) => row.searchableText.includes(query))
      : registryData.registryRows;
    return rows.slice(0, DEFAULT_VISIBLE_SOURCE_ROWS);
  }, [filter, registryData.registryRows]);

  const resultCount = useMemo(() => {
    const query = filter.trim().toLowerCase();
    return query ? registryData.registryRows.filter((row) => row.searchableText.includes(query)).length : registryData.registryRows.length;
  }, [filter, registryData.registryRows]);

  const selectedSource = useMemo(
    () => registryData.registryRows.find((row) => row.source.source_id === selectedSourceId) ?? filteredRows[0] ?? registryData.registryRows[0] ?? null,
    [filteredRows, registryData.registryRows, selectedSourceId],
  );

  useSourceTerminalMotion({
    root: rootElement,
    selectedId: selectedSource?.source.source_id ?? null,
    filterKey: `${filter}:${resultCount}`,
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      const isEditable = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || (target instanceof HTMLElement && target.isContentEditable);
      if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey && !isEditable) {
        event.preventDefault();
        filterRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const setRoot = useCallback((node: HTMLDivElement | null) => {
    rootRef.current = node;
    setRootElement(node);
  }, []);

  const clearFilter = useCallback(() => setFilter(""), []);

  return (
    <div className="source-view" aria-label="Sources">
      <div
        ref={setRoot}
        className={`source-display source-terminal${dragging ? " is-dragging" : ""}`}
        style={{ "--source-left-width": `${ratio}%` } as CSSProperties}
      >
        <SourceTerminalHeader data={registryData} />

        <div className="source-mobile-tabs" aria-label="Source panes">
          <button type="button" className={mobilePane === "rollup" ? "active" : ""} onClick={() => setMobilePane("rollup")}>
            ROLLUP
          </button>
          <button type="button" className={mobilePane === "registry" ? "active" : ""} onClick={() => setMobilePane("registry")}>
            REGISTER
          </button>
        </div>

        <div className="source-split-layout" data-mobile-pane={mobilePane}>
          <SourceRollupPane rows={registryData.rollupRows} typeRows={registryData.typeRows} totalRecords={registryData.metrics.publicRecords} />
          <SourceTerminalDivider dragging={dragging} separatorProps={separatorProps} />
          <SourceRegistryPane
            filter={filter}
            filterRef={filterRef}
            resultCount={resultCount}
            rows={filteredRows}
            selectedSource={selectedSource}
            onClearFilter={clearFilter}
            onFilterChange={setFilter}
            onSelect={setSelectedSourceId}
          />
        </div>

        <p className="source-display-note">{data.scope.ethical_note}</p>
      </div>
    </div>
  );
}

function SourceTerminalHeader({ data }: { data: ReturnType<typeof buildSourceRegistryData> }) {
  return (
    <header className="source-display-header source-terminal-header">
      <div className="source-header-title">
        <span>SOURCE REGISTER</span>
        <h2>PUBLIC SOURCE FIELD</h2>
      </div>
      <div className="source-header-status" aria-label="Source page status metrics">
        <span className="source-terminal-led is-live" aria-hidden="true" />
        <MetricCell label="SOURCE ORGS" value={data.metrics.sourceOrgs} />
        <MetricCell label="PUBLIC RECORDS" value={data.metrics.publicRecords} />
        <MetricCell label="SOURCE TYPES" value={data.metrics.sourceTypes} />
      </div>
    </header>
  );
}

function MetricCell({ label, value }: { label: string; value: number }) {
  return (
    <b className="source-metric-cell">
      <span>{label}</span>
      <strong>{numberFormat(value)}</strong>
    </b>
  );
}

function SourceRollupPane({ rows, typeRows, totalRecords }: { rows: SourceRollupRow[]; typeRows: SourceTypeRollupRow[]; totalRecords: number }) {
  const maxRecords = Math.max(...rows.map((row) => row.records), 1);

  return (
    <section className="source-pane source-rollup-pane" aria-label="Source rollup">
      <header className="source-pane-header">
        <span className="source-section-kicker">ROLLUP</span>
        <small>SOURCE FAMILY / RECORDS / SHARE / ORGS</small>
      </header>
      <div className="source-pane-scroll source-rollup-scroll">
        {rows.map((row) => (
          <div className="source-rollup-row" key={row.id} style={{ "--source-color": row.color, "--source-meter": `${Math.max(6, (row.records / maxRecords) * 100)}%` } as CSSProperties}>
            <span className={`source-family-marker source-family-marker-${row.marker}${row.records === maxRecords ? " is-active" : ""}`} aria-hidden="true" />
            <div className="source-rollup-name">
              <b title={row.label}>{row.label}</b>
              <i aria-hidden="true" />
            </div>
            <strong>{numberFormat(row.records)}</strong>
            <em>{formatPercent(row.records, totalRecords)}</em>
            <small>{String(row.orgs).padStart(2, "0")}</small>
            <SourceDotTrain value={row.records} max={maxRecords} />
          </div>
        ))}
        {typeRows.length > 0 ? (
          <>
            <div className="source-rollup-subhead" aria-hidden="true">
              <span>TYPE MIX</span>
              <small>TOP PUBLIC DISPLAY TYPES</small>
            </div>
            {typeRows.map((row) => (
              <div className="source-type-rollup-row" key={row.id} style={{ "--source-color": row.color, "--source-meter": `${Math.max(5, (row.records / maxRecords) * 100)}%` } as CSSProperties}>
                <span className="source-family-marker source-family-marker-hollow" aria-hidden="true" />
                <div className="source-rollup-name">
                  <b title={`${row.label} / ${row.familyLabel}`}>{row.label}</b>
                  <i aria-hidden="true" />
                </div>
                <strong>{numberFormat(row.records)}</strong>
                <small>{String(row.orgs).padStart(2, "0")}</small>
                <SourceDotTrain value={row.records} max={maxRecords} />
              </div>
            ))}
          </>
        ) : null}
      </div>
    </section>
  );
}

function SourceRegistryPane({
  filter,
  filterRef,
  resultCount,
  rows,
  selectedSource,
  onClearFilter,
  onFilterChange,
  onSelect,
}: {
  filter: string;
  filterRef: RefObject<HTMLInputElement | null>;
  resultCount: number;
  rows: SourceRegistryRow[];
  selectedSource: SourceRegistryRow | null;
  onClearFilter: () => void;
  onFilterChange: (value: string) => void;
  onSelect: (sourceId: number) => void;
}) {
  return (
    <section className="source-pane source-registry-pane" aria-label="Registered sources">
      <header className="source-pane-header source-registry-header">
        <div>
          <span className="source-section-kicker">REGISTERED SOURCES</span>
          <small>SOURCE ORGANISATION / PUBLIC ROLE / RECORDS / TYPE</small>
        </div>
        <SourceFilter
          refObject={filterRef}
          value={filter}
          resultCount={resultCount}
          onChange={onFilterChange}
          onClear={onClearFilter}
        />
      </header>
      <div className="source-registry-scroll" aria-label="Registered source rows">
        <div className="source-registry-column-labels" aria-hidden="true">
          <span>SOURCE ORGANISATION</span>
          <span>PUBLIC ROLE</span>
          <span>RECORDS</span>
          <span>TYPE</span>
        </div>
        {rows.map((row) => (
          <SourceRegistryRowView
            key={row.source.source_id}
            row={row}
            selected={selectedSource?.source.source_id === row.source.source_id}
            onSelect={onSelect}
          />
        ))}
      </div>
      <SourceInspector row={selectedSource} />
    </section>
  );
}

function SourceFilter({
  refObject,
  value,
  resultCount,
  onChange,
  onClear,
}: {
  refObject: RefObject<HTMLInputElement | null>;
  value: string;
  resultCount: number;
  onChange: (value: string) => void;
  onClear: () => void;
}) {
  return (
    <label className="source-filter-line">
      <span className="source-result-marker" aria-hidden="true" />
      <b>FILTER&gt;</b>
      <input
        ref={refObject}
        type="text"
        value={value}
        placeholder="_"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onClear();
          }
        }}
      />
      <em>{numberFormat(resultCount)} shown</em>
    </label>
  );
}

function SourceRegistryRowView({
  row,
  selected,
  onSelect,
}: {
  row: SourceRegistryRow;
  selected: boolean;
  onSelect: (sourceId: number) => void;
}) {
  return (
    <button
      type="button"
      className={`source-registry-row${selected ? " is-selected" : ""}`}
      data-source-id={row.source.source_id}
      onClick={() => onSelect(row.source.source_id)}
      onFocus={() => onSelect(row.source.source_id)}
      style={{ "--source-color": row.color } as CSSProperties}
      title={`${row.source.source_name} / ${row.source.source_type}`}
    >
      <i className="source-selection-bracket" aria-hidden="true" />
      <span className="source-org-name">
        <b>{row.source.source_name}</b>
        <small>{row.familyLabel}</small>
      </span>
      <span className="source-role-cell">{row.publicRole}</span>
      <strong>{numberFormat(row.recordCount)}</strong>
      <span className="source-type-cell">
        <b>{row.displayType}</b>
        <small>{row.source.publicness_level ?? "public source"}</small>
      </span>
    </button>
  );
}

function SourceInspector({ row }: { row: SourceRegistryRow | null }) {
  if (!row) {
    return null;
  }
  const dateSpan =
    row.yearStart && row.yearEnd
      ? row.yearStart === row.yearEnd
        ? String(row.yearStart)
        : `${row.yearStart}-${row.yearEnd}`
      : "undated / mixed";

  return (
    <aside className="source-inspector" aria-label="Selected source inspector">
      <div className="source-inspector-line" aria-hidden="true" />
      <header>
        <span>SELECTED SOURCE</span>
        <b>{row.source.source_name}</b>
      </header>
      <div className="source-inspector-grid">
        <SourceInspectorField label="PUBLIC ROLE" value={row.publicRole} />
        <SourceInspectorField label="FAMILY" value={row.familyLabel} />
        <SourceInspectorField label="RECORDS" value={numberFormat(row.recordCount)} />
        <SourceInspectorField label="DATE SPAN" value={dateSpan} />
        <SourceInspectorField label="NARRATIVES" value={row.narrativeLabels.slice(0, 3).join(", ") || "uncoded"} />
        <SourceInspectorField label="JURISDICTIONS" value={row.jurisdictions.slice(0, 8).join(" ") || "not mapped"} />
        {row.source.base_url ? <SourceInspectorField label="SOURCE URL" value={row.source.base_url} href={row.source.base_url} /> : null}
        {row.source.publicness_level ? <SourceInspectorField label="PUBLICNESS" value={row.source.publicness_level} /> : null}
      </div>
    </aside>
  );
}

function SourceInspectorField({ label, value, href }: { label: string; value: string; href?: string }) {
  return (
    <span>
      <b>{label}</b>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer" title={href}>
          {value}
        </a>
      ) : (
        <i title={value}>{value}</i>
      )}
    </span>
  );
}

function SourceTerminalDivider({
  dragging,
  separatorProps,
}: {
  dragging: boolean;
  separatorProps: ReturnType<typeof useSourcePaneResize>["separatorProps"];
}) {
  return (
    <div className={`source-terminal-divider${dragging ? " is-dragging" : ""}`} {...separatorProps} aria-label="Resize source panes">
      <span aria-hidden="true">┊</span>
      <b aria-hidden="true">RX</b>
      <i className="source-divider-led is-live" aria-hidden="true" />
      <i className="source-divider-led" aria-hidden="true" />
      <i className="source-divider-led hollow" aria-hidden="true" />
      <b aria-hidden="true">TX</b>
      <span aria-hidden="true">┊</span>
    </div>
  );
}

function SourceDotTrain({ value, max }: { value: number; max: number }) {
  const active = Math.max(1, Math.round((value / Math.max(1, max)) * 10));
  return (
    <span className="source-dot-train" aria-hidden="true">
      {Array.from({ length: 10 }, (_, index) => (
        <i key={index} className={index < active ? "lit" : ""} />
      ))}
    </span>
  );
}

function numberFormat(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}

function formatPercent(value: number, total: number) {
  return total ? `${Math.round((value / total) * 100)}%` : "0%";
}
