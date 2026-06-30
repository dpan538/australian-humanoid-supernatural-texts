import {
  SITE,
  absoluteUrl,
  canonicalPathForRoute,
  routeConfig,
  siteConfig,
  socialImageMetadata,
  type SiteRoutePath,
} from "@/lib/site";

type RouteStructuredDataProps = {
  path: SiteRoutePath;
};

export function RouteStructuredData({ path }: RouteStructuredDataProps) {
  const route = routeConfig(path);
  const canonicalPath = canonicalPathForRoute(route);
  const pageUrl = absoluteUrl(canonicalPath);
  const pageName = route.title === SITE.name ? SITE.name : `${route.title} | ${SITE.name}`;
  const socialImage = socialImageMetadata();

  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": route.path === "/source" ? "CollectionPage" : "WebPage",
        "@id": `${pageUrl}#webpage`,
        url: pageUrl,
        name: pageName,
        description: route.description,
        inLanguage: "en-AU",
        dateModified: siteConfig.releaseDate,
        isPartOf: {
          "@id": `${siteConfig.siteUrl}/#website`,
        },
        publisher: {
          "@id": `${siteConfig.siteUrl}/#organization`,
        },
        primaryImageOfPage: {
          "@type": "ImageObject",
          url: socialImage.url,
          width: socialImage.width,
          height: socialImage.height,
        },
        about: path === "/" ? siteConfig.searchTopics : siteConfig.keywords,
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${pageUrl}#breadcrumb`,
        itemListElement:
          canonicalPath === "/"
            ? [
                {
                  "@type": "ListItem",
                  position: 1,
                  name: SITE.name,
                  item: siteConfig.siteUrl,
                },
              ]
            : [
                {
                  "@type": "ListItem",
                  position: 1,
                  name: SITE.name,
                  item: siteConfig.siteUrl,
                },
                {
                  "@type": "ListItem",
                  position: 2,
                  name: route.title,
                  item: pageUrl,
                },
              ],
      },
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(structuredData),
      }}
    />
  );
}
