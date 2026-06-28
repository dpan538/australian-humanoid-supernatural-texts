export type FigureProfile = {
  slug: string;
  label: string;
  shortDescription: string;
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
    externalUrl: "https://en.wikipedia.org/wiki/Yowie",
    referenceLabel: "Wikipedia: Yowie",
  },
  {
    slug: "ghost",
    label: "Ghost",
    aliases: ["ghost", "ghosts", "apparition", "apparitions"],
    shortDescription:
      "Ghost and apparition records gather public accounts of visible human-like presences, haunted places, newspaper anecdotes, and later retellings. The category tracks how these figures circulate in public text rather than verifying supernatural claims.",
    externalUrl: "https://www.britannica.com/topic/ghost-spirit",
    referenceLabel: "Britannica: Ghost",
  },
  {
    slug: "spirit",
    label: "Spirit",
    aliases: ["spirit", "spirits", "spirit person", "spirit-person"],
    shortDescription:
      "Spirit-person records describe human-like supernatural presences in public texts. Some entries can sit near culturally sensitive traditions, so the archive treats this profile as a broad public-text category and preserves source context carefully.",
    externalUrl: "https://www.britannica.com/topic/spirit-religion",
    referenceLabel: "Britannica: Spirit",
  },
  {
    slug: "devil",
    label: "Devil",
    aliases: ["devil", "devils"],
    shortDescription:
      "Devil records collect public references to humanoid demonic or devil-like figures in stories, local legends, belief records, and moralised retellings. The profile is an archive category for comparing sources and periods.",
    externalUrl: "https://www.britannica.com/topic/devil",
    referenceLabel: "Britannica: Devil",
  },
  {
    slug: "giant",
    label: "Giant",
    aliases: ["giant", "giants", "ogre", "ogres"],
    shortDescription:
      "Giant and ogre records group public narratives about oversized humanoid figures, legendary beings, and retold encounters. The archive records where such figures appear in public sources, not whether the narratives are factual events.",
    externalUrl: "https://www.britannica.com/topic/giant-mythology",
    referenceLabel: "Britannica: Giant",
  },
  {
    slug: "bunyip",
    label: "Bunyip",
    aliases: ["bunyip", "bunyips"],
    shortDescription:
      "Bunyip is a long-circulating Australian public-text figure whose descriptions vary across newspapers, books, local histories, and retellings. In this archive it appears only where records meet the humanoid or humanoid-adjacent scope.",
    externalUrl: "https://en.wikipedia.org/wiki/Bunyip",
    referenceLabel: "Wikipedia: Bunyip",
  },
  {
    slug: "medicine-man",
    label: "Medicine man",
    aliases: ["medicine man", "medicine men", "medicine_man"],
    shortDescription:
      "Medicine-man references are handled as public-text records with cultural-care warnings. This profile is a cautious archive label for public records and does not reproduce or reclassify restricted knowledge.",
    externalUrl: "https://www.britannica.com/topic/medicine-man",
    referenceLabel: "Britannica: Medicine man",
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

  const displayLabel = label.trim() || "Uncoded figure";
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
