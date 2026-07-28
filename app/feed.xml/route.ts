import { indexableRecords, loadArchiveData } from "@/lib/archive-catalog";
import { recordPath } from "@/lib/archive-routing";
import { SITE, absoluteUrl } from "@/lib/site";

export const dynamic = "force-static";
export const revalidate = 86400;

export async function GET() {
  const data = await loadArchiveData();
  const records = [...indexableRecords(data)]
    .sort((a, b) => (b.year ?? -1) - (a.year ?? -1) || b.record_id - a.record_id)
    .slice(0, 50);
  const lastBuildDate = new Date(data.generated_at).toUTCString();
  const items = records
    .map((record) => {
      const link = absoluteUrl(recordPath(record));
      const publicationDate = rssDate(record.date_published);
      return `
    <item>
      <title>${xmlEscape(record.title || `Record ${record.record_id}`)}</title>
      <link>${xmlEscape(link)}</link>
      <guid isPermaLink="true">${xmlEscape(link)}</guid>
      <description>${xmlEscape(record.snippet || "Source-grounded public-text record in AusFigures.")}</description>
      ${publicationDate ? `<pubDate>${xmlEscape(publicationDate)}</pubDate>` : ""}
      <category>${xmlEscape(record.ontology_code || record.genre || "public-text record")}</category>
    </item>`;
    })
    .join("");

  const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${xmlEscape(`${SITE.name} — ${SITE.fullTitle}`)}</title>
    <link>${xmlEscape(SITE.url)}</link>
    <description>${xmlEscape(SITE.description)}</description>
    <language>en-AU</language>
    <lastBuildDate>${xmlEscape(lastBuildDate)}</lastBuildDate>
    <generator>AusFigures static archive</generator>${items}
  </channel>
</rss>`;

  return new Response(rss, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
    },
  });
}

function xmlEscape(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function rssDate(value: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : date.toUTCString();
}
