import type { RecordItem } from "@/lib/types";

export type DensityPeriodSchemeId = "historical_context" | "equal_duration" | "equal_record_count";

export type DensityPeriod = {
  id: string;
  label: string;
  start: number;
  end: number;
  shortLabel: string;
  contextLabel?: string;
  anchorNote?: string;
};

export type DensityPeriodScheme = {
  id: DensityPeriodSchemeId;
  label: string;
  description: string;
  periods: DensityPeriod[];
};

const PERIOD_COUNT = 6;

const HISTORICAL_CONTEXT_PERIOD_ANCHORS = [
  {
    start: 1825,
    end: 1850,
    shortLabel: "Early colonial",
    contextLabel: "Early colonial public records",
    anchorNote: "Early colonial public records",
  },
  {
    start: 1851,
    end: 1900,
    shortLabel: "Late colonial",
    contextLabel: "Late colonial press / Federation lead-up",
    anchorNote: "Gold-rush press expansion to Federation lead-up",
  },
  {
    start: 1901,
    end: 1918,
    shortLabel: "Federation / WWI",
    contextLabel: "Federation and First World War",
    anchorNote: "Commonwealth inauguration and First World War public-text context",
  },
  {
    start: 1919,
    end: 1945,
    shortLabel: "Interwar / WWII",
    contextLabel: "Interwar and Second World War",
    anchorNote: "Interwar and Second World War public-text context",
  },
  {
    start: 1946,
    end: 1990,
    shortLabel: "Postwar / broadcast",
    contextLabel: "Postwar / broadcast / local-history accumulation",
    anchorNote: "Postwar Australia, broadcast media, and local-history accumulation",
  },
  {
    start: 1991,
    end: null,
    shortLabel: "Web / digitisation",
    contextLabel: "Web / digitisation / repository era",
    anchorNote: "Web, digitisation, repository, and public-archive era",
  },
] as const;

export function buildDensityPeriodSchemes(records: readonly RecordItem[]): DensityPeriodScheme[] {
  const years = datedYears(records);
  const minYear = years[0] ?? 1825;
  const maxYear = years[years.length - 1] ?? new Date().getFullYear();

  return [
    buildHistoricalContextScheme(minYear, maxYear),
    buildEqualDurationScheme(minYear, maxYear),
    buildEqualRecordCountScheme(years, minYear, maxYear),
  ];
}

export function periodContainsYear(period: DensityPeriod, year: number | null | undefined) {
  return typeof year === "number" && Number.isFinite(year) && year >= period.start && year <= period.end;
}

export function datedYears(records: readonly RecordItem[]) {
  return records
    .map((record) => record.year)
    .filter((year): year is number => typeof year === "number" && Number.isFinite(year))
    .sort((a, b) => a - b);
}

function buildHistoricalContextScheme(minYear: number, maxYear: number): DensityPeriodScheme {
  return {
    id: "historical_context",
    label: "Historical Context",
    description:
      "Default public display: historical and public-text context bands. These organise source environments; they do not imply causation.",
    periods: HISTORICAL_CONTEXT_PERIOD_ANCHORS.map((anchor, index) => {
      const start = index === 0 ? Math.max(minYear, anchor.start) : anchor.start;
      const end = index === HISTORICAL_CONTEXT_PERIOD_ANCHORS.length - 1 ? maxYear : Math.min(anchor.end ?? maxYear, maxYear);
      const safeStart = Math.min(start, maxYear);
      const safeEnd = Math.max(safeStart, end);
      return {
        id: `historical-${safeStart}-${safeEnd}`,
        label: `${safeStart}-${safeEnd}`,
        start: safeStart,
        end: safeEnd,
        shortLabel: anchor.shortLabel,
        contextLabel: anchor.contextLabel,
        anchorNote: anchor.anchorNote,
      };
    }),
  };
}

function buildEqualDurationScheme(minYear: number, maxYear: number): DensityPeriodScheme {
  const span = Math.max(1, maxYear - minYear + 1);
  const binWidth = Math.ceil(span / PERIOD_COUNT);
  const periods = Array.from({ length: PERIOD_COUNT }, (_, index) => {
    const start = minYear + index * binWidth;
    const end = Math.min(maxYear, start + binWidth - 1);
    return {
      id: `duration-${start}-${end}`,
      label: `${start}-${end}`,
      start,
      end: Math.max(start, end),
      shortLabel: `Equal ${index + 1}`,
      contextLabel: "Mechanical equal-duration bin",
      anchorNote: "Generated from the current dated public-record year span",
    };
  });

  return {
    id: "equal_duration",
    label: "Equal Duration",
    description: "Comparison lens: divides the dated public-record year span into six mechanical bins.",
    periods,
  };
}

function buildEqualRecordCountScheme(years: readonly number[], minYear: number, maxYear: number): DensityPeriodScheme {
  if (!years.length) {
    return {
      id: "equal_record_count",
      label: "Equal Record Count",
      description: "Comparison lens: unavailable without dated public records.",
      periods: buildEqualDurationScheme(minYear, maxYear).periods.map((period, index) => ({
        ...period,
        id: `quantile-empty-${index}`,
        shortLabel: `Quantile ${index + 1}`,
        contextLabel: "Equal-record comparison bin",
      })),
    };
  }

  const yearCounts = new Map<number, number>();
  for (const year of years) {
    yearCounts.set(year, (yearCounts.get(year) ?? 0) + 1);
  }
  const groupedYears = [...yearCounts.entries()].sort((a, b) => a[0] - b[0]);
  const target = Math.ceil(years.length / PERIOD_COUNT);
  const bins: Array<{ start: number; end: number; count: number }> = [];
  let current: { start: number; end: number; count: number } | null = null;

  for (const [year, count] of groupedYears) {
    if (!current) {
      current = { start: year, end: year, count: 0 };
    }
    const remainingBins = PERIOD_COUNT - bins.length - 1;
    const shouldClose = current.count >= target && remainingBins > 0;
    if (shouldClose) {
      bins.push(current);
      current = { start: year, end: year, count: 0 };
    }
    current.end = year;
    current.count += count;
  }
  if (current) {
    bins.push(current);
  }

  while (bins.length < PERIOD_COUNT) {
    const lastEnd = bins[bins.length - 1]?.end ?? minYear - 1;
    const start = Math.min(maxYear, lastEnd + 1);
    bins.push({ start, end: start, count: 0 });
  }

  return {
    id: "equal_record_count",
    label: "Equal Record Count",
    description:
      "Comparison lens: splits dated public records into six near-equal groups while keeping same-year records together where possible.",
    periods: bins.slice(0, PERIOD_COUNT).map((bin, index) => ({
      id: `quantile-${bin.start}-${bin.end}-${index}`,
      label: bin.start === bin.end ? String(bin.start) : `${bin.start}-${bin.end}`,
      start: bin.start,
      end: bin.end,
      shortLabel: `Quantile ${index + 1}`,
      contextLabel: "Equal-record comparison bin",
      anchorNote: `${bin.count} dated public records in this comparison bin`,
    })),
  };
}
