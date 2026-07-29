"use client";

import Link from "next/link";
import { useDeferredValue, useId, useMemo, useRef, useState } from "react";
import type { CSSProperties, FocusEvent } from "react";
import { DisplayControls } from "@/components/display-controls";
import { useFigureDictionaryMotion } from "@/components/figures/use-figure-dictionary-motion";
import type {
  FigureDictionaryEntry,
  FigureDictionaryFrequency,
} from "@/lib/figure-dictionary-types";

export function FigureEncyclopedia({
  entries,
  initialSlug = null,
}: {
  entries: FigureDictionaryEntry[];
  initialSlug?: string | null;
}) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const rootRef = useRef<HTMLElement | null>(null);
  const [query, setQuery] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const deferredQuery = useDeferredValue(query);
  const routeEntry = entries.find((entry) => entry.slug === initialSlug) ?? null;
  const rankedResults = useMemo(
    () => rankEntries(entries, deferredQuery),
    [deferredQuery, entries],
  );
  const results = rankedResults.map((result) => result.entry);
  const suggestions = deferredQuery.trim() ? rankedResults.slice(0, 6) : [];
  const isSearching = deferredQuery.trim().length > 0;
  const termEntries = isSearching
    ? results.slice(0, 30)
    : entries.filter((entry) => entry.indexEligible).slice(0, 30);
  const activeEntry = isSearching
    ? results[0] ?? routeEntry ?? entries[0] ?? null
    : routeEntry ?? entries[0] ?? null;
  useFigureDictionaryMotion(rootRef, activeEntry?.slug ?? null);

  return (
    <main ref={rootRef} className="terminal-shell figure-dictionary-shell">
      <div className="noise-layer" aria-hidden="true" />
      <div className="terminal-stage figure-dictionary-stage">
        <section className="view-area figure-dictionary-view" aria-label="Supernatural humanoid figure dictionary">
          <header className="figure-dictionary-header">
            <Link className="figure-dictionary-brand" href="/">
              <strong>AUSFIGURES</strong>
              <span>SUPERNATURAL HUMANOID DICTIONARY</span>
            </Link>
            <nav aria-label="Archive view sequence">
              <Link href="/map">Map</Link>
              <Link href="/density">Density</Link>
              <Link href="/dashboard">Dashboard</Link>
            </nav>
          </header>

          <div className="figure-dictionary-grid">
            <aside className="figure-dictionary-browser">
              <div
                className={searchFocused ? "figure-dictionary-search-zone is-focused" : "figure-dictionary-search-zone"}
                onFocusCapture={() => setSearchFocused(true)}
                onBlurCapture={(event: FocusEvent<HTMLDivElement>) => {
                  const next = event.relatedTarget;
                  if (!(next instanceof Node) || !event.currentTarget.contains(next)) {
                    setSearchFocused(false);
                  }
                }}
              >
                {searchFocused && suggestions.length ? (
                  <button
                    className="figure-dictionary-mobile-search-backdrop"
                    type="button"
                    aria-label="Close fuzzy search suggestions"
                    onClick={() => {
                      setSearchFocused(false);
                      inputRef.current?.blur();
                    }}
                  />
                ) : null}
                <label className="figure-dictionary-search" htmlFor={inputId}>
                  <span>FUZZY SEARCH / FIGURE / ALIAS / TYPE</span>
                  <div>
                    <i aria-hidden="true">⌕</i>
                    <input
                      ref={inputRef}
                      id={inputId}
                      type="search"
                      value={query}
                      onFocus={() => setSearchFocused(true)}
                      onChange={(event) => {
                        setQuery(event.target.value);
                        setSearchFocused(true);
                      }}
                      placeholder="yowie, ghost, hairy man…"
                      autoComplete="off"
                      spellCheck={false}
                      aria-controls={`${inputId}-suggestions`}
                      aria-expanded={searchFocused && suggestions.length > 0}
                    />
                    {query ? (
                      <button type="button" onClick={() => setQuery("")} aria-label="Clear figure search">
                        CLEAR
                      </button>
                    ) : null}
                  </div>
                </label>
                {searchFocused && suggestions.length ? (
                  <div
                    className="figure-dictionary-suggestions"
                    id={`${inputId}-suggestions`}
                    role="listbox"
                    aria-label="Highest probability fuzzy matches"
                  >
                    <header>
                      <span>HIGHEST PROBABILITY</span>
                      <b>FUZZY MATCH</b>
                    </header>
                    <ol>
                      {suggestions.map(({ entry, score, matchedLabel }) => (
                        <li key={entry.slug}>
                          <Link
                            href={`/figures/${entry.slug}`}
                            role="option"
                            prefetch={false}
                            onMouseDown={(event) => event.preventDefault()}
                          >
                            <span>
                              <strong>{entry.label}</strong>
                              <small>
                                {matchedLabel === entry.label ? "PRIMARY LABEL" : `MATCHED: ${matchedLabel}`}
                              </small>
                            </span>
                            <b>{Math.round(score * 100)}%</b>
                          </Link>
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}
              </div>

              <nav className="figure-dictionary-term-field" aria-label="Figure search terms">
                <header>
                  <span>{isSearching ? "FUZZY MATCH TERMS" : "HIGH-FREQUENCY TERMS"}</span>
                  <b>{isSearching ? "SELECT A MATCH" : "DIRECT ACCESS"}</b>
                </header>
                {termEntries.length ? (
                  <div>
                    {termEntries.map((entry) => (
                      <Link
                        href={`/figures/${entry.slug}`}
                        key={entry.slug}
                        className={activeEntry?.slug === entry.slug ? "is-active" : undefined}
                        prefetch={false}
                      >
                        {entry.label}
                      </Link>
                    ))}
                  </div>
                ) : (
                  <p>NO MATCH — TRY ANOTHER SPELLING OR ALIAS</p>
                )}
              </nav>
            </aside>

            <section className="figure-dictionary-results" aria-live="polite">
              {activeEntry ? (
                <FigureDictionaryDashboard entry={activeEntry} />
              ) : (
                <div className="figure-dictionary-empty">
                  <span>NO MATCH</span>
                  <p>Try a broader public-text term, alias, narrative type, or switch the index scope.</p>
                </div>
              )}
            </section>
          </div>
        </section>

        <div className="terminal-footer-controls figure-dictionary-footer">
          <DisplayControls />
          <div className="external-control-dock" aria-label="Fixed external controls">
            <Link className="dock-button about-button" href="/about">About</Link>
            <Link className="dock-button source-button" href="/source">Source</Link>
            <Link
              className="dock-button view-cycle-button active"
              href="/map"
              aria-label="Current view Figures; switch to Map"
              title="Switch to Map"
            >
              <span className="view-label-current">Figures</span>
              <span className="view-label-next">Map</span>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}

function FigureDictionaryDashboard({ entry }: { entry: FigureDictionaryEntry }) {
  const mappedShare = entry.recordCount ? (entry.mappedCount / entry.recordCount) * 100 : 0;
  const primaryName = entry.nameFrequency[0]?.label ?? entry.label;

  return (
    <article className="figure-dictionary-dashboard">
      <header className="figure-dictionary-profile-header">
        <div className="figure-dictionary-profile-route">
          <span>DICTIONARY ENTRY</span>
          <b>{String(entry.rank).padStart(3, "0")} / {entry.indexEligible ? "PUBLIC" : "REVIEW"}</b>
        </div>
        <div className="figure-dictionary-profile-identity">
          <div>
            <span>SUPERNATURAL HUMANOID FIGURE</span>
            <h1>{entry.label}</h1>
            <p>
              {entry.aliases.length
                ? `Also indexed as ${entry.aliases.slice(0, 5).join(", ")}.`
                : `Primary indexed name: ${primaryName}.`}
            </p>
          </div>
          <div className="figure-dictionary-record-total">
            <span>PUBLIC-TEXT OCCURRENCES</span>
            <strong>{formatNumber(entry.recordCount)}</strong>
            <small>{entry.corpusShare.toFixed(2)}% OF PUBLIC CORPUS</small>
          </div>
        </div>
      </header>

      <section className="figure-dictionary-kpi-grid" aria-label={`${entry.label} summary statistics`}>
        <MetricCard
          label="LEADING REGION"
          value={entry.regionFrequency[0]?.label ?? "Not coded"}
          note={entry.regionFrequency[0] ? `${formatNumber(entry.regionFrequency[0].count)} coded records` : "no regional concentration"}
        />
        <MetricCard label="DOCUMENTED SPAN" value={entry.dateSpan} note="accepted dated records" />
        <MetricCard
          label="MAPPED EVIDENCE"
          value={formatNumber(entry.mappedCount)}
          note={`${mappedShare.toFixed(1)}% geographically mapped`}
        />
      </section>

      <section className="figure-dictionary-editorial-summary">
        <span>ARCHIVE SUMMARY</span>
        <p>{entry.editorialSummary}</p>
      </section>

      {entry.recordCount ? (
        <>
          <div className="figure-dictionary-primary-visuals">
            {entry.corpusShare < 1 ? (
              <ArchiveSignalPanel entry={entry} />
            ) : (
              <section className="figure-dictionary-viz-card figure-dictionary-share-card">
                <VizHeader label="CORPUS PRESENCE" note="record share" />
                <div className="figure-dictionary-share-value">
                  <strong>{entry.corpusShare.toFixed(2)}%</strong>
                  <span>{formatNumber(entry.recordCount)} / {formatNumber(entry.corpusTotal)}</span>
                </div>
                <SegmentMeter percentage={Math.min(100, entry.corpusShare)} segments={28} />
                <small>Archive frequency, not a prevalence estimate.</small>
              </section>
            )}
            {entry.timeline.length >= 3 && entry.recordCount >= 12 ? (
              <TimelinePanel rows={entry.timeline} />
            ) : entry.timeline.length >= 3 ? (
              <SparseTimelinePanel rows={entry.timeline} />
            ) : (
              <DocumentClusterPanel rows={entry.timeline} recordCount={entry.recordCount} />
            )}
          </div>

          <FigureSecondaryVisuals entry={entry} />
        </>
      ) : (
        <NoStatisticalBasisPanel entry={entry} />
      )}

      <div className="figure-dictionary-evidence-grid">
        <section className="figure-dictionary-records">
          <header>
            <h2>SELECTED PUBLIC RECORDS</h2>
            <span>
              {entry.records.length < entry.recordCount
                ? `${entry.records.length} OF ${formatNumber(entry.recordCount)}`
                : `${entry.records.length} RECORDS`}
            </span>
          </header>
          {entry.records.length ? (
            <ol>
              {entry.records.map((record, index) => (
                <li key={record.href}>
                  <Link href={record.href}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{record.title}</strong>
                    <small>
                      {[record.year ?? "Undated", record.place]
                        .filter(Boolean)
                        .join(" / ")}
                    </small>
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <p className="figure-dictionary-no-records">
              No search-ready public record currently supports this taxonomy entry.
            </p>
          )}
        </section>
        <section className="figure-dictionary-related-card">
          <VizHeader label="RELATED SEARCH PATHS" note="shared archive fields" />
          {entry.related.length ? (
            <div>
              {entry.related.map((item) => (
                <Link href={item.href} key={item.href}>
                  <strong>{item.label}</strong>
                  <span aria-hidden="true">↗</span>
                </Link>
              ))}
            </div>
          ) : (
            <p>No adjacent indexed figures.</p>
          )}
        </section>
      </div>

      <footer className="figure-dictionary-detail-footer">
        <a href={entry.externalReference.href} target="_blank" rel="noopener noreferrer">
          {entry.externalReference.label}
        </a>
        <Link href="/data">DATA & INDEX POLICY</Link>
        <Link href="/cite">CITATION GUIDE</Link>
      </footer>
    </article>
  );
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

function VizHeader({ label, note }: { label: string; note: string }) {
  return (
    <header className="figure-dictionary-viz-header">
      <h2>{label}</h2>
      <span>{note}</span>
    </header>
  );
}

function SegmentMeter({ percentage, segments }: { percentage: number; segments: number }) {
  const activeSegments = Math.max(percentage > 0 ? 1 : 0, Math.round((percentage / 100) * segments));
  return (
    <div className="figure-dictionary-segment-meter" aria-label={`${percentage.toFixed(2)} percent`}>
      {Array.from({ length: segments }, (_, index) => (
        <i className={index < activeSegments ? "is-active" : undefined} key={index} />
      ))}
    </div>
  );
}

function ArchiveSignalPanel({ entry }: { entry: FigureDictionaryEntry }) {
  const threshold = Math.max(1, Math.ceil(entry.corpusTotal * 0.01));
  const thresholdShare = Math.min(100, (entry.recordCount / threshold) * 100);

  return (
    <section className="figure-dictionary-viz-card figure-dictionary-archive-signal">
      <VizHeader label="ARCHIVE SIGNAL" note="one dot per record / 1% threshold" />
      <div className="figure-dictionary-threshold-waffle">
        <div
          className="figure-dictionary-threshold-dots"
          role="img"
          aria-label={`${entry.recordCount} active record dots out of a one-percent threshold of ${threshold}`}
        >
          {Array.from({ length: threshold }, (_, index) => (
            <i className={index < entry.recordCount ? "is-active" : undefined} key={index} />
          ))}
        </div>
        <div>
          <strong>{formatNumber(entry.recordCount)}</strong>
          <span>OF {formatNumber(threshold)} RECORDS</span>
          <small>Each filled point is one accepted public record.</small>
        </div>
      </div>
      <footer>
        <strong>{thresholdShare.toFixed(1)}%</strong>
        <span>of the 1% archive threshold</span>
        <b>1% = {formatNumber(threshold)} records</b>
      </footer>
      <small>Scale describes archive representation, not real-world prevalence.</small>
    </section>
  );
}

function TimelinePanel({ rows }: { rows: FigureDictionaryFrequency[] }) {
  const max = Math.max(...rows.map((row) => row.count), 1);
  return (
    <section className="figure-dictionary-viz-card figure-dictionary-timeline-card">
      <VizHeader label="OCCURRENCE TIMELINE" note="records by decade" />
      {rows.length ? (
        <>
          <div className="figure-dictionary-timeline-bars" aria-label="Occurrence count by decade">
            {rows.map((row) => (
              <i
                key={row.label}
                title={`${row.label}: ${formatNumber(row.count)} records`}
                style={{ "--figure-bar-height": `${Math.max(7, (row.count / max) * 100)}%` } as CSSProperties}
              />
            ))}
          </div>
          <div className="figure-dictionary-timeline-axis">
            <span>{rows[0]?.label}</span>
            <b>PEAK {formatNumber(max)}</b>
            <span>{rows.at(-1)?.label}</span>
          </div>
        </>
      ) : (
        <p className="figure-dictionary-viz-empty">No dated records.</p>
      )}
    </section>
  );
}

function SparseTimelinePanel({ rows }: { rows: FigureDictionaryFrequency[] }) {
  const width = 420;
  const height = 180;
  const left = 26;
  const right = 394;
  const baseline = 142;
  const plotHeight = 94;
  const max = Math.max(...rows.map((row) => row.count), 1);
  const points = rows.map((row, index) => {
    const ratio = rows.length === 1 ? 0.5 : index / (rows.length - 1);
    return {
      ...row,
      x: left + ratio * (right - left),
      y: baseline - (row.count / max) * plotHeight,
    };
  });
  const pointString = points.map((point) => `${point.x},${point.y}`).join(" ");
  const areaString = `${left},${baseline} ${pointString} ${right},${baseline}`;

  return (
    <section className="figure-dictionary-viz-card figure-dictionary-sparse-timeline">
      <VizHeader label="SPARSE TEMPORAL TRACE" note="exact dated counts" />
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Sparse dated record trace">
        <line className="is-baseline" x1={left} y1={baseline} x2={right} y2={baseline} />
        <polygon points={areaString} />
        <polyline points={pointString} />
        {points.map((point) => (
          <g key={point.label}>
            <line className="is-guide" x1={point.x} y1={point.y} x2={point.x} y2={baseline} />
            <circle cx={point.x} cy={point.y} r="5" />
            <text className="is-count" x={point.x} y={point.y - 12}>{formatNumber(point.count)}</text>
            <text className="is-label" x={point.x} y={baseline + 22}>{point.label}</text>
          </g>
        ))}
      </svg>
      <small>Each vertex is an observed decade count; the filled field only joins coded observations.</small>
    </section>
  );
}

function DocumentClusterPanel({
  rows,
  recordCount,
}: {
  rows: FigureDictionaryFrequency[];
  recordCount: number;
}) {
  return (
    <section className="figure-dictionary-viz-card figure-dictionary-document-clusters">
      <VizHeader label="DOCUMENT CLUSTERS" note="one point per record" />
      {rows.length ? (
        <>
          <div className="figure-dictionary-cluster-summary">
            <strong>{formatNumber(recordCount)}</strong>
            <span>
              {rows.length === 1
                ? `records concentrated in one coded decade`
                : `records distributed across ${rows.length} coded decades`}
            </span>
          </div>
          <ol aria-label="Document count by coded decade">
            {rows.map((row) => (
              <li key={row.label}>
                <span>{row.label}</span>
                <div title={`${row.label}: ${formatNumber(row.count)} records`}>
                  {Array.from({ length: row.count }, (_, index) => (
                    <i key={index} />
                  ))}
                </div>
                <b>{formatNumber(row.count)}</b>
              </li>
            ))}
          </ol>
          <small>
            Individual points retain small-sample scale; they do not imply a continuous trend.
          </small>
        </>
      ) : (
        <p className="figure-dictionary-viz-empty">
          {formatNumber(recordCount)} undated {recordCount === 1 ? "record" : "records"}.
        </p>
      )}
    </section>
  );
}

function FigureSecondaryVisuals({ entry }: { entry: FigureDictionaryEntry }) {
  const isMinorityFigure = entry.corpusShare < 1;

  return (
    <div
      className={`figure-dictionary-secondary-visuals${isMinorityFigure ? " is-minority" : ""}`}
      aria-label={`${entry.label} secondary archive statistics`}
    >
      {isMinorityFigure ? (
        <>
          <RareFigureCompositionPanel entry={entry} />
          <RecordCompletenessPanel entry={entry} />
        </>
      ) : (
        <>
          <RegionFieldPanel rows={entry.regionFrequency} total={entry.recordCount} />
          <SourceConcentrationPanel
            rows={entry.sourceFrequency}
            sourceCount={entry.sourceCount}
            total={entry.recordCount}
          />
        </>
      )}
    </div>
  );
}

function RegionFieldPanel({
  rows,
  total,
}: {
  rows: FigureDictionaryFrequency[];
  total: number;
}) {
  const populatedRows = rows.filter((row) => row.count > 0);
  const chartRows =
    populatedRows.length > 8
      ? [
          ...populatedRows.slice(0, 7),
          {
            label: "Other coded regions",
            count: populatedRows.slice(7).reduce((sum, row) => sum + row.count, 0),
            href: null,
          },
        ]
      : populatedRows;
  const codedTotal = chartRows.reduce((sum, row) => sum + row.count, 0);
  const apportionedRows = apportionRegionalCells(chartRows, 100);
  const cells = apportionedRows.flatMap((row, rowIndex) =>
    Array.from({ length: row.cells }, (_, cellIndex) => ({
      key: `${row.label}-${cellIndex}`,
      label: row.label,
      tone: rowIndex + 1,
    })),
  );
  const coverage = total ? Math.min(100, (codedTotal / total) * 100) : 0;

  return (
    <section className="figure-dictionary-viz-card figure-dictionary-region-field">
      <VizHeader label="REGIONAL FIELD" note={`${formatNumber(codedTotal)} region-coded records`} />
      {chartRows.length ? (
        <div className="figure-dictionary-region-field-body">
          <div className="figure-dictionary-region-plot">
            <div
              className="figure-dictionary-region-waffle"
              role="img"
              aria-label={`Regional composition of ${formatNumber(codedTotal)} coded records. Each cell represents one percent of the region-coded subset.`}
            >
              {cells.map((cell) => (
                <i
                  aria-hidden="true"
                  className={`is-region-${cell.tone}`}
                  key={cell.key}
                  title={cell.label}
                />
              ))}
            </div>
            <p>
              <strong>{coverage.toFixed(1)}%</strong>
              <span>of this figure&apos;s records include a coded region</span>
            </p>
          </div>
          <ol>
            {chartRows.map((row, index) => (
              <li key={row.label}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{row.label}</strong>
                <b>{formatNumber(row.count)}</b>
                <small>{codedTotal ? `${((row.count / codedTotal) * 100).toFixed(1)}%` : "0%"}</small>
              </li>
            ))}
          </ol>
          <small className="figure-dictionary-region-note">
            One cell equals 1% of the region-coded subset; exact record counts remain listed at right.
          </small>
        </div>
      ) : (
        <p className="figure-dictionary-viz-empty">No coded regional distribution.</p>
      )}
    </section>
  );
}

function apportionRegionalCells(
  rows: FigureDictionaryFrequency[],
  totalCells: number,
) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  if (!total) {
    return rows.map((row) => ({ ...row, cells: 0 }));
  }

  const apportioned = rows.map((row, index) => {
    const exact = (row.count / total) * totalCells;
    return {
      ...row,
      cells: Math.floor(exact),
      remainder: exact - Math.floor(exact),
      index,
    };
  });
  let cellsLeft = totalCells - apportioned.reduce((sum, row) => sum + row.cells, 0);
  const remainderOrder = [...apportioned].sort(
    (left, right) => right.remainder - left.remainder || left.index - right.index,
  );

  for (let index = 0; index < cellsLeft; index += 1) {
    remainderOrder[index % remainderOrder.length].cells += 1;
  }

  return apportioned
    .sort((left, right) => left.index - right.index)
    .map((row) => ({
      label: row.label,
      count: row.count,
      href: row.href,
      cells: row.cells,
    }));
}

function SourceConcentrationPanel({
  rows,
  sourceCount,
  total,
}: {
  rows: FigureDictionaryFrequency[];
  sourceCount: number;
  total: number;
}) {
  const chartRows = rows.slice(0, 5);
  const max = Math.max(...chartRows.map((row) => row.count), 1);
  const leadingShare = total && chartRows[0] ? (chartRows[0].count / total) * 100 : 0;

  return (
    <section className="figure-dictionary-viz-card figure-dictionary-source-concentration">
      <VizHeader label="SOURCE CONCENTRATION" note={`${sourceCount} organisations`} />
      {chartRows.length ? (
        <>
          <div className="figure-dictionary-source-summary">
            <strong>{leadingShare.toFixed(1)}%</strong>
            <span>held by the leading source</span>
          </div>
          <ol>
            {chartRows.map((row, index) => (
              <li key={row.label}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{row.label}</strong>
                  <i>
                    <b style={{ "--figure-source-width": `${Math.max(3, (row.count / max) * 100)}%` } as CSSProperties} />
                  </i>
                </div>
                <b>{formatNumber(row.count)}</b>
              </li>
            ))}
          </ol>
        </>
      ) : (
        <p className="figure-dictionary-viz-empty">No public source concentration.</p>
      )}
    </section>
  );
}

function RareFigureCompositionPanel({ entry }: { entry: FigureDictionaryEntry }) {
  const sourceRows = compactCompositionRows(entry.sourceFrequency);
  const narrativeRows = compactCompositionRows(entry.narrativeFrequency);

  return (
    <section className="figure-dictionary-viz-card figure-dictionary-rare-composition">
      <VizHeader label="ARCHIVE COMPOSITION" note="source constellation / baseline bubbles" />
      <div className="figure-dictionary-composition-views">
        <SourceConstellation rows={sourceRows} />
        <NarrativeBubbleBaseline rows={narrativeRows} />
      </div>
      <small>
        Every constellation point is a record; bubble area encodes exact narrative share within this archive sample.
      </small>
    </section>
  );
}

function compactCompositionRows(
  rows: FigureDictionaryFrequency[],
  limit = 4,
): FigureDictionaryFrequency[] {
  if (rows.length <= limit) {
    return rows;
  }
  const visible = rows.slice(0, limit - 1);
  const remainder = rows.slice(limit - 1).reduce((sum, row) => sum + row.count, 0);
  return [...visible, { label: "Other coded rows", count: remainder, href: null }];
}

function SourceConstellation({ rows }: { rows: FigureDictionaryFrequency[] }) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const centers = constellationCenters(rows.length);

  return (
    <section className="figure-dictionary-source-constellation">
      <h3>SOURCE CONSTELLATION</h3>
      {rows.length ? (
        <div>
          <svg viewBox="0 0 360 225" role="img" aria-label="Source constellation; one point per public record">
            <line className="is-axis" x1="24" y1="198" x2="336" y2="198" />
            {rows.map((row, index) => {
              const center = centers[index] ?? centers.at(-1) ?? { x: 180, y: 100 };
              const points = constellationPoints(row.count, center.x, center.y);
              return (
                <g className={`tone-${index + 1}`} key={row.label}>
                  <line className="is-stem" x1={center.x} y1={center.y} x2={center.x} y2="198" />
                  {points.map((point, pointIndex) => (
                    <circle
                      className={pointIndex % 5 === 4 ? "is-record is-cadence" : "is-record"}
                      cx={point.x}
                      cy={point.y}
                      r={pointIndex % 5 === 4 ? "5" : "3.4"}
                      key={pointIndex}
                    />
                  ))}
                  <circle className="is-centroid" cx={center.x} cy={center.y} r={7 + Math.min(3, Math.sqrt(row.count))} />
                  <text x={center.x} y={center.y + 4}>{formatNumber(row.count)}</text>
                </g>
              );
            })}
          </svg>
          <ol>
            {rows.map((row, index) => (
              <li key={row.label}>
                <i className={`tone-${index + 1}`} aria-hidden="true" />
                <strong>{row.label}</strong>
                <b>{formatNumber(row.count)}</b>
                <small>{total ? `${((row.count / total) * 100).toFixed(0)}%` : "0%"}</small>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <p>No coded source constellation.</p>
      )}
    </section>
  );
}

function constellationCenters(count: number) {
  if (count <= 1) return [{ x: 180, y: 105 }];
  if (count === 2) return [{ x: 110, y: 105 }, { x: 250, y: 105 }];
  if (count === 3) {
    return [{ x: 180, y: 62 }, { x: 105, y: 145 }, { x: 255, y: 145 }];
  }
  return [
    { x: 105, y: 62 },
    { x: 255, y: 62 },
    { x: 105, y: 145 },
    { x: 255, y: 145 },
  ];
}

function constellationPoints(count: number, centerX: number, centerY: number) {
  const extent = Math.max(2, Math.ceil(Math.sqrt(count)));
  const offsets: Array<{ x: number; y: number }> = [];
  for (let y = -extent; y <= extent; y += 1) {
    for (let x = -extent; x <= extent; x += 1) {
      if (x !== 0 || y !== 0) {
        offsets.push({ x, y });
      }
    }
  }
  offsets.sort((a, b) => {
    const distanceDifference = (a.x ** 2 + a.y ** 2) - (b.x ** 2 + b.y ** 2);
    return distanceDifference || a.y - b.y || a.x - b.x;
  });
  return Array.from({ length: count }, (_, index) => {
    const offset = offsets[index] ?? { x: 0, y: 0 };
    return {
      x: centerX + offset.x * 17,
      y: centerY + offset.y * 17,
    };
  });
}

function NarrativeBubbleBaseline({ rows }: { rows: FigureDictionaryFrequency[] }) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const spacing = 300 / Math.max(rows.length, 1);

  return (
    <section className="figure-dictionary-narrative-baseline">
      <h3>NARRATIVE BUBBLE BASELINE</h3>
      {rows.length ? (
        <div>
          <svg viewBox="0 0 360 230" role="img" aria-label="Narrative type baseline bubbles; area encodes record share">
            <line className="is-baseline" x1="24" y1="158" x2="336" y2="158" />
            {rows.map((row, index) => {
              const share = total ? row.count / total : 0;
              const x = 30 + spacing * (index + 0.5);
              const radius = Math.min(58, 17 + Math.sqrt(share) * 48);
              const y = 158 - radius;
              return (
                <g className={`tone-${index + 1}`} key={row.label}>
                  <circle cx={x} cy={y} r={radius} />
                  <text className="is-index" x={x} y={y + 4}>{String(index + 1).padStart(2, "0")}</text>
                  <line className="is-stem" x1={x} y1="158" x2={x} y2="218" />
                  <text className="is-count" x={x} y="181">{formatNumber(row.count)}</text>
                  <text className="is-share" x={x} y="207">{(share * 100).toFixed(0)}%</text>
                </g>
              );
            })}
          </svg>
          <ol>
            {rows.map((row, index) => (
              <li key={row.label}>
                <i className={`tone-${index + 1}`} aria-hidden="true" />
                <strong>{row.label}</strong>
                <b>{formatNumber(row.count)}</b>
                <small>{total ? `${((row.count / total) * 100).toFixed(0)}%` : "0%"}</small>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <p>No coded narrative types.</p>
      )}
    </section>
  );
}

function RecordCompletenessPanel({ entry }: { entry: FigureDictionaryEntry }) {
  const datedCount = entry.timeline.reduce((sum, row) => sum + row.count, 0);
  const regionCodedCount = entry.regionFrequency.reduce((sum, row) => sum + row.count, 0);
  const completenessRows = [
    {
      label: "DATED",
      count: datedCount,
      percentage: entry.recordCount ? (datedCount / entry.recordCount) * 100 : 0,
    },
    {
      label: "REGION CODED",
      count: regionCodedCount,
      percentage: entry.recordCount ? (regionCodedCount / entry.recordCount) * 100 : 0,
    },
    {
      label: "MAPPED",
      count: entry.mappedCount,
      percentage: entry.recordCount ? (entry.mappedCount / entry.recordCount) * 100 : 0,
    },
  ];

  return (
    <section className="figure-dictionary-viz-card figure-dictionary-record-completeness">
      <VizHeader label="RECORD COMPLETENESS" note={`${entry.recordCount} record sample`} />
      <div className="figure-dictionary-completeness-summary">
        <div>
          <strong>{entry.timeline.length}</strong>
          <span>coded decades</span>
        </div>
        <div>
          <strong>{entry.sourceCount}</strong>
          <span>source organisations</span>
        </div>
        <div>
          <strong>{entry.placeCount}</strong>
          <span>coded regions</span>
        </div>
      </div>
      <div className="figure-dictionary-completeness-plot">
        {completenessRows.map((row) => (
          <div key={row.label}>
            <span>{row.label}</span>
            <i>
              <b
                style={{
                  "--figure-completeness-width": `${Math.max(row.percentage > 0 ? 4 : 0, row.percentage)}%`,
                } as CSSProperties}
              />
            </i>
            <strong>{formatNumber(row.count)} / {formatNumber(entry.recordCount)}</strong>
          </div>
        ))}
      </div>
      <small>
        Metadata completeness, not supernatural prevalence or evidential strength.
      </small>
    </section>
  );
}

function NoStatisticalBasisPanel({ entry }: { entry: FigureDictionaryEntry }) {
  return (
    <section className="figure-dictionary-no-statistics">
      <header>
        <span>STATISTICAL VIEW WITHHELD</span>
        <b>0 SEARCH-READY RECORDS</b>
      </header>
      <div>
        <strong>{entry.label}</strong>
        <p>
          This dictionary entry is retained for taxonomy and associated-search coverage,
          but the public archive currently has no record-level basis for a distribution,
          trend, regional, or source chart.
        </p>
      </div>
      <dl>
        <div>
          <dt>TAXONOMY ENTRIES</dt>
          <dd>{entry.taxonomy.length}</dd>
        </div>
        <div>
          <dt>KNOWN ALIASES</dt>
          <dd>{entry.aliases.length}</dd>
        </div>
        <div>
          <dt>INDEX STATUS</dt>
          <dd>REVIEW / NOINDEX</dd>
        </div>
      </dl>
    </section>
  );
}

type FigureDictionaryMatch = {
  entry: FigureDictionaryEntry;
  score: number;
  matchedLabel: string;
};

function rankEntries(
  entries: FigureDictionaryEntry[],
  query: string,
): FigureDictionaryMatch[] {
  const normalized = normalizeSearchValue(query);

  if (!normalized) {
    return entries.map((entry) => ({ entry, score: 1, matchedLabel: entry.label }));
  }

  return entries
    .map((entry) => scoreEntry(entry, normalized))
    .filter((match) => match.score >= fuzzyThreshold(normalized))
    .sort(
      (a, b) =>
        b.score - a.score ||
        b.entry.recordCount - a.entry.recordCount ||
        a.entry.label.localeCompare(b.entry.label),
    );
}

function scoreEntry(entry: FigureDictionaryEntry, query: string): FigureDictionaryMatch {
  const candidates = [
    entry.label,
    ...entry.aliases,
    ...entry.printedLabels,
    ...entry.taxonomy.map((item) => item.name),
  ];
  let best = { score: 0, matchedLabel: entry.label };
  for (const candidate of candidates) {
    const score = fuzzySimilarity(query, normalizeSearchValue(candidate));
    if (score > best.score) {
      best = { score, matchedLabel: candidate };
    }
  }
  if (normalizeSearchValue(entry.searchText).includes(query)) {
    best.score = Math.max(best.score, 0.68);
  }
  return {
    entry,
    score: Math.min(1, best.score),
    matchedLabel: best.matchedLabel,
  };
}

function fuzzySimilarity(query: string, candidate: string) {
  if (!candidate) {
    return 0;
  }
  if (candidate === query) {
    return 1;
  }
  if (candidate.startsWith(query)) {
    return Math.min(0.97, 0.9 + (query.length / candidate.length) * 0.07);
  }
  if (candidate.includes(query)) {
    return Math.min(0.9, 0.8 + (query.length / candidate.length) * 0.1);
  }
  const queryTokens = query.split(" ").filter(Boolean);
  const tokenCoverage = queryTokens.length
    ? queryTokens.filter((token) => candidate.includes(token)).length / queryTokens.length
    : 0;
  const editSimilarity = normalizedEditSimilarity(query, candidate);
  const bigramSimilarity = diceCoefficient(query, candidate);
  const subsequenceSimilarity = subsequenceScore(query, candidate);
  return Math.max(
    tokenCoverage * 0.82,
    editSimilarity * 0.88,
    bigramSimilarity * 0.84,
    subsequenceSimilarity * 0.72,
  );
}

function normalizeSearchValue(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/[^a-z0-9 ]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizedEditSimilarity(a: string, b: string) {
  const maxLength = Math.max(a.length, b.length);
  if (!maxLength) {
    return 1;
  }
  const previous = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let row = 1; row <= a.length; row += 1) {
    let diagonal = previous[0];
    previous[0] = row;
    for (let column = 1; column <= b.length; column += 1) {
      const above = previous[column];
      const cost = a[row - 1] === b[column - 1] ? 0 : 1;
      previous[column] = Math.min(
        previous[column] + 1,
        previous[column - 1] + 1,
        diagonal + cost,
      );
      diagonal = above;
    }
  }
  return 1 - previous[b.length] / maxLength;
}

function diceCoefficient(a: string, b: string) {
  if (a.length < 2 || b.length < 2) {
    return a === b ? 1 : 0;
  }
  const pairs = new Map<string, number>();
  for (let index = 0; index < a.length - 1; index += 1) {
    const pair = a.slice(index, index + 2);
    pairs.set(pair, (pairs.get(pair) ?? 0) + 1);
  }
  let intersection = 0;
  for (let index = 0; index < b.length - 1; index += 1) {
    const pair = b.slice(index, index + 2);
    const count = pairs.get(pair) ?? 0;
    if (count > 0) {
      intersection += 1;
      pairs.set(pair, count - 1);
    }
  }
  return (2 * intersection) / (a.length + b.length - 2);
}

function subsequenceScore(query: string, candidate: string) {
  let queryIndex = 0;
  let firstMatch = -1;
  let lastMatch = -1;
  for (let index = 0; index < candidate.length && queryIndex < query.length; index += 1) {
    if (candidate[index] === query[queryIndex]) {
      if (firstMatch === -1) {
        firstMatch = index;
      }
      lastMatch = index;
      queryIndex += 1;
    }
  }
  if (queryIndex !== query.length) {
    return 0;
  }
  const span = lastMatch - firstMatch + 1;
  return (query.length / Math.max(span, 1)) * (query.length / candidate.length);
}

function fuzzyThreshold(query: string) {
  if (query.length <= 2) {
    return 0.78;
  }
  if (query.length <= 4) {
    return 0.42;
  }
  return 0.34;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-AU").format(value);
}
