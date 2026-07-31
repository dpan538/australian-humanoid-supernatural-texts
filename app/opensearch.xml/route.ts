import { SITE, absoluteUrl } from "@/lib/site";

export const dynamic = "force-static";

export function GET() {
  const searchTemplate = `${absoluteUrl("/figures")}?q={searchTerms}`;
  const suggestionsTemplate = `${absoluteUrl(SITE.searchSuggestionsPath)}?q={searchTerms}`;
  const selfUrl = absoluteUrl(SITE.openSearchPath);
  const document = `<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>${xmlEscape(SITE.name)}</ShortName>
  <Description>Search Australian supernatural humanoid figures, aliases, and public-text records in AusFigures.</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
  <Image width="16" height="16" type="image/x-icon">${xmlEscape(absoluteUrl(SITE.faviconPath))}</Image>
  <Image width="192" height="192" type="image/png">${xmlEscape(absoluteUrl(SITE.pngIconPath))}</Image>
  <Url type="text/html" template="${xmlEscape(searchTemplate)}" />
  <Url type="application/x-suggestions+json" template="${xmlEscape(suggestionsTemplate)}" />
  <Url type="application/opensearchdescription+xml" rel="self" template="${xmlEscape(selfUrl)}" />
  <SearchForm>${xmlEscape(absoluteUrl("/figures"))}</SearchForm>
</OpenSearchDescription>`;

  return new Response(document, {
    headers: {
      "Content-Type": "application/opensearchdescription+xml; charset=utf-8",
      "Cache-Control": "public, max-age=86400, s-maxage=604800, stale-while-revalidate=2592000",
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
