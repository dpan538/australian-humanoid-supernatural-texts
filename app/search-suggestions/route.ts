import { loadArchiveData } from "@/lib/archive-catalog";
import { buildFigureDictionaryEntries } from "@/lib/figure-dictionary";
import { figurePath } from "@/lib/archive-routing";
import { absoluteUrl } from "@/lib/site";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const query = new URL(request.url).searchParams.get("q")?.trim() ?? "";
  const normalizedQuery = normalize(query);
  const data = await loadArchiveData();
  const results = buildFigureDictionaryEntries(data)
    .filter((entry) => entry.recordCount > 0)
    .map((entry) => ({ entry, score: suggestionScore(entry.label, entry.aliases, normalizedQuery) }))
    .filter(({ score }) => score > 0)
    .sort((left, right) => right.score - left.score || right.entry.recordCount - left.entry.recordCount)
    .slice(0, 10);

  return Response.json(
    [
      query,
      results.map(({ entry }) => entry.label),
      results.map(({ entry }) => `${entry.recordCount.toLocaleString("en-AU")} public-text records`),
      results.map(({ entry }) => absoluteUrl(figurePath(entry.slug))),
    ],
    {
      headers: {
        "Cache-Control": "public, max-age=300, s-maxage=86400, stale-while-revalidate=604800",
      },
    },
  );
}

function suggestionScore(label: string, aliases: string[], query: string) {
  if (!query) return 1;
  return Math.max(...[label, ...aliases].map((candidate) => scoreCandidate(normalize(candidate), query)));
}

function scoreCandidate(candidate: string, query: string) {
  if (candidate === query) return 100;
  if (candidate.startsWith(query)) return 90 - Math.min(20, candidate.length - query.length);
  if (candidate.split(" ").some((word) => word.startsWith(query))) return 78;
  if (candidate.includes(query)) return 68;
  if (isSubsequence(query, candidate)) return 42;
  return 0;
}

function normalize(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function isSubsequence(query: string, candidate: string) {
  let index = 0;
  for (const character of candidate) {
    if (character === query[index]) index += 1;
    if (index === query.length) return true;
  }
  return false;
}
