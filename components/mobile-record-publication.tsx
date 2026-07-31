"use client";

import Link from "next/link";
import { useId, useState } from "react";
import {
  MobileArchiveControls,
  MobileCardDeck,
  MobileExpandableCard,
  MobileLinkArrowIcon,
  MobileTopBar,
  type MobileFigureSearchEntry,
} from "@/components/mobile-archive";
import {
  STATE_NAMES,
  narrativeTypeName,
  narrativeTypePath,
  recordPath,
  sourcePath,
} from "@/lib/archive-routing";
import type { RecordItem } from "@/lib/types";

export function MobileRecordPublication({
  record,
  related,
  figures,
  description,
  figureLabel,
  figureHref,
  indexEligible,
}: {
  record: RecordItem;
  related: RecordItem[];
  figures: MobileFigureSearchEntry[];
  description: string;
  figureLabel: string | null;
  figureHref: string | null;
  indexEligible: boolean;
}) {
  const summaryId = useId();
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const title = record.title || `Public record #${record.record_id}`;
  const narrativeCode = record.ontology_code || record.genre;
  const place = record.state_territory
    ? STATE_NAMES[record.state_territory] ?? record.state_territory
    : record.map_place_name || "Not mapped";

  return (
    <main className="terminal-shell mobile-archive-shell mobile-record-shell">
      <h1 className="visually-hidden">{title} — AusFigures public-text record</h1>
      <MobileTopBar
        view="figures"
        figures={figures}
        routeLabel={`RECORD · ${record.record_id}`}
      />
      <section className="mobile-archive-page mobile-record-page">
        <header className="mobile-record-hero">
          <span>PUBLIC-TEXT RECORD / {indexEligible ? "INDEXED" : "REVIEW"}</span>
          <h2>{title}</h2>
          <button
            type="button"
            className={`mobile-record-summary ${summaryExpanded ? "is-expanded" : ""}`.trim()}
            aria-expanded={summaryExpanded}
            aria-controls={summaryId}
            onClick={() => setSummaryExpanded((current) => !current)}
          >
            <span id={summaryId}>{description}</span>
            <small>
              {summaryExpanded ? "Show less" : "Read record summary"}
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d="m7.5 9.5 4.5 4.5 4.5-4.5" />
              </svg>
            </small>
          </button>
          <dl className="mobile-record-primary-stats">
            <div>
              <dt>YEAR</dt>
              <dd>{record.year ?? "Undated"}</dd>
            </div>
            <div>
              <dt>PLACE</dt>
              <dd>{place}</dd>
            </div>
            <div>
              <dt>SOURCE</dt>
              <dd>{record.source_name || "Unspecified"}</dd>
            </div>
          </dl>
        </header>

        <MobileCardDeck className="mobile-record-card-deck">
          <MobileExpandableCard
            cardId="record-fields"
            tone="mint"
            eyebrow="ARCHIVE FIELDS"
            title="Record Context"
            metric={figureLabel || narrativeCode ? "Coded public text" : "Public text"}
          >
            <dl className="mobile-record-fields">
              <div><dt>RECORD ID</dt><dd>{record.record_id}</dd></div>
              <div><dt>FIGURE</dt><dd>{figureLabel || "Unspecified"}</dd></div>
              <div><dt>NARRATIVE</dt><dd>{narrativeTypeName(narrativeCode || "unspecified")}</dd></div>
              <div><dt>PRINTED LABEL</dt><dd>{record.figure_name_as_printed || "Not retained"}</dd></div>
              <div><dt>PUBLICATION</dt><dd>{record.publication || "Not specified"}</dd></div>
              <div><dt>AUTHOR</dt><dd>{record.author || "Not specified"}</dd></div>
            </dl>
          </MobileExpandableCard>

          <MobileExpandableCard
            cardId="record-source"
            tone="coral"
            eyebrow="PUBLIC SOURCE"
            title="Source Context"
            metric={record.source_name || "Source retained"}
          >
            <blockquote className="mobile-record-excerpt">
              {record.snippet || description}
            </blockquote>
            <p className="mobile-record-note">
              Terminology belongs to the cited public source. Its presence in the
              archive is not verification of the reported claim.
            </p>
            {record.url ? (
              <a
                className="mobile-record-link"
                href={record.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span>Open original public source</span>
                <MobileLinkArrowIcon />
              </a>
            ) : null}
          </MobileExpandableCard>

          <MobileExpandableCard
            cardId="record-browse"
            tone="yellow"
            eyebrow="CONNECTED INDEX"
            title="Browse Archive"
            metric="Figure · type · source"
          >
            <nav className="mobile-record-browse" aria-label="Browse connected archive fields">
              {figureHref && figureLabel ? (
                <Link href={figureHref}>
                  <span><small>FIGURE</small><b>{figureLabel}</b></span>
                  <MobileLinkArrowIcon />
                </Link>
              ) : null}
              {narrativeCode ? (
                <Link href={narrativeTypePath(narrativeCode)}>
                  <span><small>NARRATIVE TYPE</small><b>{narrativeTypeName(narrativeCode)}</b></span>
                  <MobileLinkArrowIcon />
                </Link>
              ) : null}
              {record.source_name ? (
                <Link href={sourcePath(record.source_id, record.source_name)}>
                  <span><small>SOURCE</small><b>{record.source_name}</b></span>
                  <MobileLinkArrowIcon />
                </Link>
              ) : null}
            </nav>
          </MobileExpandableCard>

          {related.length ? (
            <MobileExpandableCard
              cardId="record-related"
              tone="lavender"
              eyebrow="PUBLIC TEXT"
              title="Related Records"
              metric={`${related.length} paths`}
            >
              <ol className="mobile-record-related">
                {related.slice(0, 6).map((item, index) => (
                  <li key={item.record_id}>
                    <Link href={recordPath(item)}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <b>{item.title || `Public record #${item.record_id}`}</b>
                      <small>
                        {[item.year ?? "Undated", item.source_name]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                      <MobileLinkArrowIcon />
                    </Link>
                  </li>
                ))}
              </ol>
            </MobileExpandableCard>
          ) : null}
        </MobileCardDeck>
      </section>
      <MobileArchiveControls view="figures" />
    </main>
  );
}
