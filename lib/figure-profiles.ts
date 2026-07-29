export type FigureProfile = {
  slug: string;
  label: string;
  shortDescription: string;
  archiveDescription?: string;
  externalUrl: string;
  referenceLabel: string;
  aliases?: string[];
  notes?: string;
};

export const FIGURE_PROFILES: FigureProfile[] = [
  {
    slug: "yowie",
    label: "Yowie",
    aliases: ["yowie", "yahoo"],
    shortDescription:
      "Yowie is a public-text figure associated with hairy humanoid reports, bush encounters, local retellings, and later Australian cryptid discourse. In this archive it is treated as a source-grounded narrative category, not as evidence for a real creature.",
    archiveDescription:
      "Across encounter reports, Yowie is usually described as a large, heavily haired, upright or human-shaped figure seen briefly in bushland, beside roads, or near the edge of settlements. Accounts commonly emphasise height, an ape-like outline, tracks, calls, or a rapid retreat from witnesses.",
    externalUrl: "https://en.wikipedia.org/wiki/Yowie",
    referenceLabel: "Wikipedia: Yowie",
  },
  {
    slug: "ghost",
    label: "Ghost",
    aliases: ["ghost", "ghosts", "apparition", "apparitions"],
    shortDescription:
      "Ghost and apparition records gather public accounts of visible human-like presences, haunted places, newspaper anecdotes, and later retellings. The category tracks how these figures circulate in public text rather than verifying supernatural claims.",
    archiveDescription:
      "Apparition accounts describe recognisably human figures, voices, silhouettes, or presences associated with a deceased person or a particular house, road, mine, prison, or homestead. Many survive as place-linked anecdotes and later retellings rather than direct witness testimony.",
    externalUrl: "https://www.britannica.com/topic/ghost-spirit",
    referenceLabel: "Britannica: Ghost",
  },
  {
    slug: "spirit",
    label: "Spirit",
    aliases: ["spirit", "spirits", "spirit person", "spirit-person"],
    shortDescription:
      "Spirit-person records describe human-like supernatural presences in public texts. Some entries can sit near culturally sensitive traditions, so the archive treats this profile as a broad public-text category and preserves source context carefully.",
    archiveDescription:
      "Public sources use spirit-person wording for human-like presences, named beings, ancestral figures, and other culturally specific persons. Their appearance and role vary substantially between sources, and many records describe belief, ceremony, or retelling rather than an eyewitness encounter.",
    externalUrl: "https://www.britannica.com/topic/spirit-religion",
    referenceLabel: "Britannica: Spirit",
  },
  {
    slug: "devil",
    label: "Devil",
    aliases: ["devil", "devils"],
    shortDescription:
      "Devil records collect public references to humanoid demonic or devil-like figures in stories, local legends, belief records, and moralised retellings. The profile is an archive category for comparing sources and periods.",
    archiveDescription:
      "Records describe dark, horned, monstrous, or otherwise human-like devil figures appearing in local legends, moralised stories, place names, and reported encounters. The printed term is broad: some uses name a visible figure, while others are figurative or literary.",
    externalUrl: "https://www.britannica.com/topic/devil",
    referenceLabel: "Britannica: Devil",
  },
  {
    slug: "giant",
    label: "Giant",
    aliases: ["giant", "giants", "ogre", "ogres"],
    shortDescription:
      "Giant and ogre records group public narratives about oversized humanoid figures, legendary beings, and retold encounters. The archive records where such figures appear in public sources, not whether the narratives are factual events.",
    archiveDescription:
      "Accounts and retellings describe unusually large human-shaped beings, oversized tracks, or powerful ogre-like figures. Most of the material circulates as legend, belief record, or literary adaptation rather than as a modern sighting report.",
    externalUrl: "https://www.britannica.com/topic/giant-mythology",
    referenceLabel: "Britannica: Giant",
  },
  {
    slug: "bunyip",
    label: "Bunyip",
    aliases: ["bunyip", "bunyips"],
    shortDescription:
      "Bunyip is a long-circulating Australian public-text figure whose descriptions vary across newspapers, books, local histories, and retellings. In this archive it appears only where records meet the humanoid or humanoid-adjacent scope.",
    archiveDescription:
      "Descriptions range from animal-like water creatures to vaguely upright or human-like beings associated with swamps, lagoons, billabongs, and riverbanks. The archive includes only the records that meet its humanoid or humanoid-adjacent scope, so this card does not represent every printed Bunyip account.",
    externalUrl: "https://en.wikipedia.org/wiki/Bunyip",
    referenceLabel: "Wikipedia: Bunyip",
  },
  {
    slug: "medicine-man",
    label: "Medicine man",
    aliases: ["medicine man", "medicine men", "medicine_man"],
    shortDescription:
      "Medicine-man references are handled as public-text records with cultural-care warnings. This profile is a cautious archive label for public records and does not reproduce or reclassify restricted knowledge.",
    archiveDescription:
      "Historical public sources use this label for ritual specialists and describe healing, divination, ceremony, weather-making, or other attributed powers. These are source-bound colonial descriptions; the entry does not treat the term as a single identity or reproduce restricted knowledge.",
    externalUrl: "https://www.britannica.com/topic/medicine-man",
    referenceLabel: "Britannica: Medicine man",
  },
  {
    slug: "hairy-man",
    label: "Hairy Man",
    shortDescription:
      "Hairy Man gathers public-text descriptions of heavily haired, human-shaped figures while keeping the printed label and source context visible. It overlaps with Yowie discourse but is not treated as a synonym for every Yowie or culturally specific Hairy People tradition.",
    archiveDescription:
      "Encounter-style records describe an unidentified, human-shaped and heavily haired figure, sometimes compared with a Yahoo, Australian ape, or Australian gorilla and encountered in bush or rural settings. Similar printed wording in culturally specific sources remains source-bound rather than being collapsed into one tradition.",
    externalUrl:
      "https://en.wikipedia.org/w/index.php?search=Australian+Hairy+Man+folklore",
    referenceLabel: "Reference search",
  },
  {
    slug: "fishers-ghost",
    label: "Fisher's Ghost",
    shortDescription:
      "Fisher's Ghost is a named Australian apparition tradition associated with the disappearance and death of Frederick Fisher near Campbelltown in 1826 and its later public retellings.",
    archiveDescription:
      "The best-known account describes a human-looking apparition in ordinary nineteenth-century clothing at a Campbelltown slip-panel, reportedly pointing toward the paddock where Frederick Fisher's body was later found. The archive also captures the story's repetition in books, newspapers, and local-history retellings.",
    externalUrl: "https://en.wikipedia.org/wiki/Fisher%27s_ghost",
    referenceLabel: "Wikipedia: Fisher's Ghost",
  },
  {
    slug: "baiame",
    label: "Baiame",
    shortDescription:
      "Baiame appears in historical public texts through culturally specific descriptions that require careful attribution and should not be collapsed into a generic supernatural figure.",
    archiveDescription:
      "Historical public sources describe Baiame as a creator or law-giving figure and sometimes recount former appearances, instruction, or departure. This archive presents those missionary, colonial, and later public descriptions as source history rather than as an authoritative account of living cultural knowledge.",
    externalUrl: "https://en.wikipedia.org/wiki/Baiame",
    referenceLabel: "Wikipedia: Baiame",
  },
  {
    slug: "wirreenun",
    label: "Wirreenun",
    shortDescription:
      "Wirreenun is retained as a source-bound historical public-text label for a culturally specific role, with cultural-care limits applied to interpretation and display.",
    archiveDescription:
      "Historical public texts use Wirreenun for a ritual specialist or medicine man and describe prayer, healing, rainmaking, crystal stones, or totemic powers. These are colonial-era source descriptions, not a contemporary cultural definition or a claim that every printed account refers to the same practice.",
    externalUrl:
      "https://en.wikipedia.org/w/index.php?search=Wirreenun",
    referenceLabel: "Reference search",
  },
];

export function figureProfileFor(label: string): FigureProfile {
  const normalized = normalizeFigureLabel(label);
  const profile = FIGURE_PROFILES.find((item) => {
    if (normalizeFigureLabel(item.label) === normalized || item.slug === normalized) {
      return true;
    }
    return item.aliases?.some((alias) => normalizeFigureLabel(alias) === normalized);
  });

  if (profile) {
    return profile;
  }

  const displayLabel = titleCaseFigureLabel(label.trim() || "Uncoded figure");
  return {
    slug: normalized || "uncoded-figure",
    label: displayLabel,
    shortDescription: `${displayLabel} is represented here as a public-text figure category. This card summarises how records using or implying this label appear in the archive, including period coverage, mapped share, source context, and regional concentration. It does not verify the underlying supernatural claim.`,
    externalUrl: `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(displayLabel)}`,
    referenceLabel: "Reference search",
  };
}

export function normalizeFigureLabel(label: string) {
  return label.trim().toLowerCase().replace(/[_\s]+/g, "-").replace(/[^a-z0-9-]/g, "").replace(/-+/g, "-").replace(/^-|-$/g, "");
}

function titleCaseFigureLabel(label: string) {
  return label
    .replace(/_/g, " ")
    .replace(/\S+/g, (word) => `${word.charAt(0).toLocaleUpperCase("en-AU")}${word.slice(1)}`);
}
