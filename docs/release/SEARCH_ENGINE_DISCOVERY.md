# Search Engine Discovery

Use this note after each production deployment when submitting AusFigures to public search and AI discovery surfaces.

## Canonical Inputs

- Canonical origin: `https://ausfigures.com`
- Homepage and primary map entry: `https://ausfigures.com/`
- Sitemap: `https://ausfigures.com/sitemap.xml`
- Robots: `https://ausfigures.com/robots.txt`
- AI context: `https://ausfigures.com/llms.txt`
- Expanded AI context: `https://ausfigures.com/llms-full.txt`

## Search Engines

Submit the sitemap URL rather than individual route aliases wherever the tool supports sitemap submission.

- Google Search Console: submit `https://ausfigures.com/sitemap.xml`, inspect `/`, `/source`, `/density`, `/about`, `/topics`, and the topic pages after deploy.
- Bing Webmaster Tools: add the property, verify ownership, submit `https://ausfigures.com/sitemap.xml`, and request URL indexing for the homepage and topic index.
- Baidu Search Resource Platform: add the site, verify ownership, submit the sitemap URL if the account supports sitemap submission, and keep `Baiduspider` allowed in robots.
- Yandex Webmaster: add the site, verify ownership, submit the sitemap URL, and inspect the canonical homepage.
- DuckDuckGo: no direct site-submit path is required for this launch; keep Bing and standard sitemap/robots metadata clean because DuckDuckGo uses multiple upstream sources.
- Applebot and Safari surfaces: rely on canonical metadata, Open Graph, icons, manifest, and standard crawler access.
- Naver, Sogou, Seznam, Yahoo, and other mainstream crawlers: keep robots open, sitemap canonical, route metadata clean, and no `vercel.app` canonical URLs.

## IndexNow

IndexNow can be added later for faster Bing/Yandex-style URL discovery, but it requires a site key file and a ping workflow. Do not add a fake key or submit pings from local development. If enabled later, use the production canonical URLs only:

- `https://ausfigures.com/`
- `https://ausfigures.com/dashboard`
- `https://ausfigures.com/density`
- `https://ausfigures.com/source`
- `https://ausfigures.com/about`
- `https://ausfigures.com/topics`
- topic pages under `https://ausfigures.com/topics/`

## AI Discovery

The public AI-facing files are intentionally conservative:

- `llms.txt` is the concise public entry.
- `llms-full.txt` is the expanded public-safe context for answer engines and AI crawlers.
- Structured data exposes the project as `Organization`, `WebSite`, and `Dataset`.
- Topic pages provide public search-language landing pages without changing the archive's research semantics.

Do not add private notes, restricted source material, raw data paths, local paths, internal review files, unpublished cultural material, or secrets to AI-facing files.

## Search Snippet Rules

Use this framing in metadata, snippets, and webmaster descriptions:

- "Source-grounded public-text archive"
- "Australian supernatural humanoid narratives and encounters"
- "Public records and public metadata"
- "Markers are public display locations, not proof, habitats, or populations"

Avoid:

- "verified supernatural sightings"
- "monster map"
- "haunted tourism guide"
- "proof database"
- "complete folklore census"
- "official Indigenous knowledge repository"

## After Deploy

1. Fetch `https://ausfigures.com/robots.txt` and confirm it references the sitemap.
2. Fetch `https://ausfigures.com/sitemap.xml` and confirm every URL uses the apex domain.
3. Inspect `https://ausfigures.com/` in Google Search Console and confirm Dataset structured data has no `spatialCoverage` or `license` warnings.
4. Search for `site:ausfigures.com AusFigures` after indexing begins and check that the title, snippet, and icon are professional.
5. Submit the sitemap in Bing and Google first; use Baidu and Yandex after account verification is ready.
