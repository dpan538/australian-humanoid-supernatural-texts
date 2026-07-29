import { SITE, siteConfig } from "@/lib/site";

export type CitationSample = {
  id: "apa" | "chicago" | "mla" | "bibtex";
  label: string;
  text: string;
};

export function buildProjectCitations(generatedDate: string): CitationSample[] {
  const generatedLong = formatCitationDate(generatedDate, "long");
  const generatedMla = formatCitationDate(generatedDate, "mla");
  const accessedDate = siteConfig.contentUpdatedDate;
  const accessedMla = formatCitationDate(accessedDate, "mla");
  const generatedYear = generatedDate.slice(0, 4);
  const generatedMonth = generatedDate.slice(5, 7);
  const generatedDay = generatedDate.slice(8, 10);
  const bibliographyAuthor = "Pan, Dai";

  return [
    {
      id: "apa",
      label: "APA 7",
      text: `Pan, D. (${generatedYear}). ${SITE.fullTitle} (Public export generated ${generatedLong}) [Data set and digital archive]. ${SITE.url}/`,
    },
    {
      id: "chicago",
      label: "Chicago",
      text: `${bibliographyAuthor}. “${SITE.fullTitle}.” Digital archive and dataset. Public export generated ${generatedLong}. ${SITE.url}/.`,
    },
    {
      id: "mla",
      label: "MLA 9",
      text: `${bibliographyAuthor}. “${SITE.fullTitle}.” ${SITE.name}, public export generated ${generatedMla}, ${SITE.domain}. Accessed ${accessedMla}.`,
    },
    {
      id: "bibtex",
      label: "BibTeX",
      text: `@dataset{pan_ausfigures_${generatedYear},
  author       = {Pan, Dai},
  title        = {${SITE.fullTitle}},
  year         = {${generatedYear}},
  month        = {${generatedMonth}},
  day          = {${generatedDay}},
  publisher    = {AusFigures},
  version      = {Public export ${generatedDate}},
  url          = {${SITE.url}/},
  urldate      = {${accessedDate}},
  note         = {Source-grounded digital archive; cite the original public source for record-level claims}
}`,
    },
  ];
}

function formatCitationDate(value: string, style: "long" | "mla") {
  const date = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  if (style === "mla") {
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }).format(date);
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}
