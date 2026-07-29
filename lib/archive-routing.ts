import type { RecordItem } from "@/lib/types";

export const STATE_NAMES: Record<string, string> = {
  WA: "Western Australia",
  NT: "Northern Territory",
  SA: "South Australia",
  QLD: "Queensland",
  NSW: "New South Wales",
  VIC: "Victoria",
  TAS: "Tasmania",
  ACT: "Australian Capital Territory",
};

export const NARRATIVE_TYPE_NAMES: Record<string, string> = {
  cryptid_style_apeman: "Hairy Humanoid and Wild-Person Accounts",
  encounter_account: "Encounter Accounts",
  apparition_account: "Ghost and Apparition Accounts",
  ghost_legend: "Ghost Legends",
  local_legend: "Local Legends",
  rumour_account: "Rumour Accounts",
  traditional_narrative: "Traditional Narratives",
  spirit_person_narrative: "Spirit-Person Narratives",
  spirit_being: "Spirit-Being Records",
  ancestral_being: "Ancestral-Being Records",
  giant_or_ogre_narrative: "Giant and Ogre Narratives",
  giant: "Giant Narratives",
  cautionary_being: "Cautionary-Being Narratives",
  descriptive_belief_record: "Descriptive Belief Records",
  reported_encounter: "Reported Encounters",
  retelling_or_adaptation: "Retellings and Adaptations",
  other_supernatural_humanoid_or_adjacent: "Other Supernatural Humanoid or Adjacent Records",
  satire: "Satirical Public Texts",
};

export function archiveSlug(value: string | null | undefined, fallback = "record") {
  const slug = (value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-")
    .slice(0, 84)
    .replace(/-+$/g, "");
  return slug || fallback;
}

export function humanizeArchiveCode(value: string | null | undefined) {
  if (!value) {
    return "Unspecified";
  }
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function narrativeTypeName(code: string) {
  return NARRATIVE_TYPE_NAMES[code] ?? humanizeArchiveCode(code);
}

export function recordRouteSlug(record: Pick<RecordItem, "record_id" | "title">) {
  return `${record.record_id}-${archiveSlug(record.title, "public-text-record")}`;
}

export function recordPath(record: Pick<RecordItem, "record_id" | "title">) {
  return `/records/${recordRouteSlug(record)}`;
}

export function recordIdFromRouteSlug(slug: string) {
  const match = slug.match(/^(\d+)(?:-|$)/);
  return match ? Number(match[1]) : null;
}

export function recordsPagePath(page: number) {
  return page <= 1 ? "/records" : `/records/page/${page}`;
}

export function narrativeTypePath(code: string) {
  return `/narrative-types/${archiveSlug(code, "unspecified")}`;
}

export function labelKey(value: string | null | undefined) {
  return (value ?? "Unspecified")
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function figurePath(slug: string) {
  return `/figures/${archiveSlug(slug, "uncoded-figure")}`;
}

export function sourcePath(sourceId: number, sourceName: string) {
  return `/sources/${sourceId}-${archiveSlug(sourceName, "public-source")}`;
}

export function sourceIdFromRouteSlug(slug: string) {
  const match = slug.match(/^(\d+)(?:-|$)/);
  return match ? Number(match[1]) : null;
}

export function placePath(stateCode: string) {
  return `/places/${archiveSlug(stateCode)}`;
}

export function periodPath(periodId: string) {
  return `/periods/${archiveSlug(periodId)}`;
}
