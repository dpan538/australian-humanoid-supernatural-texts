export type FigureDictionaryLink = {
  href: string;
  label: string;
};

export type FigureDictionaryRecord = {
  href: string;
  title: string;
  year: number | null;
  source: string;
  place: string | null;
  narrative: string;
};

export type FigureDictionaryTaxonomy = {
  name: string;
  cluster: string;
  humanoidDegree: string;
  status: string;
  description: string | null;
  sensitivityNote: string | null;
};

export type FigureDictionaryFrequency = {
  label: string;
  count: number;
  href: string | null;
};

export type FigureDictionaryEntry = {
  slug: string;
  label: string;
  description: string;
  editorialSummary: string;
  aliases: string[];
  printedLabels: string[];
  rank: number;
  recordCount: number;
  sourceCount: number;
  placeCount: number;
  mappedCount: number;
  corpusShare: number;
  corpusTotal: number;
  dateSpan: string;
  indexEligible: boolean;
  nameFrequency: FigureDictionaryFrequency[];
  regionFrequency: FigureDictionaryFrequency[];
  periodFrequency: FigureDictionaryFrequency[];
  sourceFrequency: FigureDictionaryFrequency[];
  narrativeFrequency: FigureDictionaryFrequency[];
  timeline: FigureDictionaryFrequency[];
  narratives: FigureDictionaryLink[];
  places: FigureDictionaryLink[];
  sources: FigureDictionaryLink[];
  periods: FigureDictionaryLink[];
  records: FigureDictionaryRecord[];
  related: Array<FigureDictionaryLink & { recordCount: number }>;
  taxonomy: FigureDictionaryTaxonomy[];
  externalReference: FigureDictionaryLink;
  searchText: string;
};
