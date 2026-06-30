import { absoluteUrl } from "@/lib/site";

export type SeoTopic = {
  slug: string;
  title: string;
  eyebrow: string;
  description: string;
  summary: string;
  scope: string;
  interpretation: string;
  queryTerms: string[];
};

export const seoTopics = [
  {
    slug: "australian-supernatural",
    title: "Australian Supernatural Public Texts",
    eyebrow: "Research Topic",
    description:
      "A research entry point for Australian supernatural public texts in AusFigures, covering humanoid narratives, apparitions, ghosts, Yowie, bunyip, spirit-person narratives, and related public records.",
    summary:
      "This topic gathers the main search language around Australian supernatural records while keeping the archive framed as public-text research. AusFigures tracks how claims, figures, and labels appear in public sources, not whether any claim is true.",
    scope:
      "Relevant records may include published encounters, local legends, newspaper accounts, public-domain books, repository metadata, institutional pages, and retellings where a humanoid or humanoid-adjacent figure is part of the public text.",
    interpretation:
      "Search terms such as Australian supernatural, Australian folklore, and supernatural encounters can refer to entertainment, tourism, belief, or research. This archive uses those terms only as public-text categories and discovery language.",
    queryTerms: [
      "Australian supernatural",
      "Australian supernatural folklore",
      "Australian folklore archive",
      "Australian legends and encounters",
    ],
  },
  {
    slug: "supernatural-humanoids",
    title: "Australian Supernatural Humanoids",
    eyebrow: "Narrative Scope",
    description:
      "A source-grounded overview of Australian supernatural humanoid and humanoid-adjacent narratives represented in AusFigures public records.",
    summary:
      "AusFigures focuses on humanoid or humanoid-adjacent supernatural figures as they appear in Australian public texts. The scope can include named figures, broad labels, local descriptions, apparition accounts, and retellings.",
    scope:
      "The archive separates public record context from claim verification. A record may show that a source exists, that a figure label was used, or that a place was associated with a narrative; it does not prove a supernatural event.",
    interpretation:
      "Humanoid is used as a research scope marker, not as a biological, habitat, or population claim.",
    queryTerms: [
      "Australian supernatural humanoids",
      "supernatural humanoid narratives",
      "humanoid supernatural encounters",
      "Australian humanoid legends",
    ],
  },
  {
    slug: "yowie-records",
    title: "Yowie Records in Public Texts",
    eyebrow: "Figure Label",
    description:
      "A research entry point for Yowie records and public-text references in AusFigures, with map and source context rather than proof claims.",
    summary:
      "Yowie is one of the search terms most likely to bring users into the archive. AusFigures treats Yowie entries as public-text records and figure-label signals, not as proof of an animal, person, habitat, or population.",
    scope:
      "Relevant records may include public web pages, newspapers, local histories, books, repository items, and retellings where the Yowie label or a closely related hairy humanoid figure is part of the source record.",
    interpretation:
      "Mapped markers for Yowie-related records are display locations for public records. They do not indicate verified sightings or distribution.",
    queryTerms: ["Yowie records", "Yowie map", "Australian Yowie archive", "Yowie public texts"],
  },
  {
    slug: "bunyip-public-texts",
    title: "Bunyip Public Texts",
    eyebrow: "Figure Label",
    description:
      "A source-grounded research entry for bunyip references in Australian public texts where records meet the AusFigures humanoid or humanoid-adjacent scope.",
    summary:
      "Bunyip appears across Australian newspapers, books, local histories, and retellings with varied descriptions. AusFigures includes bunyip-related material only where the record fits the archive scope and public-source policy.",
    scope:
      "The topic is useful for users searching bunyip, Australian folklore, or public-domain Australian supernatural texts, while keeping the project clear that inclusion is a public-source signal.",
    interpretation:
      "The archive does not treat bunyip records as a complete folklore census or as evidence for a real-world population.",
    queryTerms: ["bunyip public texts", "bunyip records", "Australian bunyip folklore", "bunyip archive"],
  },
  {
    slug: "australian-ghosts-apparitions",
    title: "Australian Ghost and Apparition Records",
    eyebrow: "Narrative Type",
    description:
      "A research entry point for Australian ghost and apparition records in public sources, including newspaper accounts, local histories, and retellings.",
    summary:
      "Ghost and apparition records in AusFigures are public-text categories. They may describe visible presences, haunted places, local legends, or later retellings, but the archive does not verify the underlying supernatural claim.",
    scope:
      "This topic helps users searching for Australian ghosts, apparitions, haunted narratives, or public folklore records find the source register, map, and density views.",
    interpretation:
      "Place associations are display locations for records and should not be read as haunted tourism guidance.",
    queryTerms: [
      "Australian ghost records",
      "Australian apparition records",
      "Australian haunted public records",
      "Australian ghost legends",
    ],
  },
  {
    slug: "spirit-person-narratives",
    title: "Spirit-Person Narratives",
    eyebrow: "Sensitive Scope",
    description:
      "A cautious research entry for spirit-person narratives in Australian public texts, with attention to publicness, terminology, source voice, and cultural sensitivity.",
    summary:
      "Spirit-person is used here as a broad public-text category. Some records sit near culturally sensitive traditions, so the archive emphasises publicness, source context, terminology, and display limits.",
    scope:
      "The topic may include public records where human-like supernatural presences appear in published or public metadata contexts. It is not an official Indigenous knowledge repository.",
    interpretation:
      "Public discoverability does not grant permission to extract restricted cultural knowledge, and search visibility must not flatten source voice or community context.",
    queryTerms: [
      "spirit-person narratives",
      "Australian spirit narratives",
      "Australian public text archive",
      "Indigenous-related public records sensitivity",
    ],
  },
] as const satisfies readonly SeoTopic[];

export type SeoTopicSlug = (typeof seoTopics)[number]["slug"];

export function topicPath(slug: SeoTopicSlug | string) {
  return `/topics/${slug}`;
}

export function topicUrl(slug: SeoTopicSlug | string) {
  return absoluteUrl(topicPath(slug));
}

export function topicBySlug(slug: string) {
  return seoTopics.find((topic) => topic.slug === slug);
}
