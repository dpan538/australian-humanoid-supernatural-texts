export const INDEXED_STATIC_PATHS = [
  "/",
  "/dashboard",
  "/density",
  "/source",
  "/about",
  "/figures",
  "/data",
  "/cite",
] as const;

export const INDEXED_FIGURE_SLUGS = [
  "yowie",
  "hairy-man",
  "fishers-ghost",
  "bunyip",
] as const;

const indexedFigureSlugs = new Set<string>(INDEXED_FIGURE_SLUGS);

export function isIndexedFigureSlug(slug: string) {
  return indexedFigureSlugs.has(slug);
}

export const INTENDED_SITEMAP_URL_COUNT =
  INDEXED_STATIC_PATHS.length + INDEXED_FIGURE_SLUGS.length;
