import type { Metadata, Viewport } from "next";
import Script from "next/script";
import { SITE, absoluteUrl, siteConfig, socialCardImageMetadata } from "@/lib/site";
import "./globals.css";
import "./mobile.css";

const socialImage = socialCardImageMetadata({
  title: "Australian Supernatural Humanoid Public-Text Archive",
  description: SITE.description,
  eyebrow: "AUSTRALIAN PUBLIC ARCHIVE",
  metric: "4,265 records",
  tone: "paper",
});
const twitterImage = socialImage;
const logoUrl = absoluteUrl(SITE.logoPath);
const licenseUrl = `${siteConfig.repositoryUrl}/blob/main/LICENSE.md`;
const datasetDownloadUrl = absoluteUrl("/data/frontend-data.json");

const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${siteConfig.siteUrl}/#organization`,
      name: siteConfig.siteName,
      alternateName: siteConfig.fullTitle,
      url: siteConfig.siteUrl,
      logo: {
        "@type": "ImageObject",
        url: logoUrl,
        width: 512,
        height: 512,
      },
      sameAs: [siteConfig.repositoryUrl],
    },
    {
      "@type": "WebSite",
      "@id": `${siteConfig.siteUrl}/#website`,
      name: siteConfig.siteName,
      alternateName: [
        siteConfig.fullTitle,
        "Australian supernatural public-text archive",
        "Australian supernatural humanoid archive",
      ],
      url: siteConfig.siteUrl,
      description: siteConfig.shortDescription,
      inLanguage: "en-AU",
      datePublished: siteConfig.releaseDate,
      dateModified: siteConfig.contentUpdatedDate,
      publisher: {
        "@id": `${siteConfig.siteUrl}/#organization`,
      },
      creator: {
        "@type": "Person",
        name: siteConfig.creator,
      },
      isAccessibleForFree: true,
      potentialAction: {
        "@type": "SearchAction",
        target: {
          "@type": "EntryPoint",
          urlTemplate: `${absoluteUrl("/figures")}?q={search_term_string}`,
        },
        "query-input": "required name=search_term_string",
      },
      hasPart: [
        {
          "@type": "WebPage",
          name: "AusFigures Research Dashboard",
          url: absoluteUrl("/dashboard"),
          about: "Archive coverage across records, figures, sources, periods, and mapped locations",
        },
        {
          "@type": "WebPage",
          name: "AusFigures Density Explorer",
          url: absoluteUrl("/density"),
          about: "Time, source, figure, and mapped-location signals in the public-text archive",
        },
        {
          "@type": "CollectionPage",
          name: "Australian Supernatural Humanoid Encyclopedia",
          url: absoluteUrl("/figures"),
          about: [
            "Australian supernatural humanoid figures",
            "rare Australian folklore figures",
            "public-text figure categories",
          ],
        },
        {
          "@type": "CollectionPage",
          name: "AusFigures Source Register",
          url: absoluteUrl("/source"),
          about: "Public source organisations, source families, and archive provenance",
        },
        {
          "@type": "AboutPage",
          name: "AusFigures Research Method",
          url: absoluteUrl("/about"),
          about: "Source policy, research method, audit protocol, mapping limits, and ethics",
        },
      ],
    },
    {
      "@type": "Dataset",
      "@id": `${siteConfig.siteUrl}/#dataset`,
      identifier: siteConfig.siteUrl,
      name: siteConfig.fullTitle,
      alternateName: siteConfig.siteName,
      url: siteConfig.siteUrl,
      sameAs: siteConfig.repositoryUrl,
      description: siteConfig.shortDescription,
      inLanguage: "en-AU",
      datePublished: siteConfig.releaseDate,
      dateModified: siteConfig.contentUpdatedDate,
      publisher: {
        "@id": `${siteConfig.siteUrl}/#organization`,
      },
      creator: {
        "@type": "Person",
        name: siteConfig.creator,
      },
      isAccessibleForFree: true,
      spatialCoverage: {
        "@type": "Place",
        name: "Australia",
        geo: {
          "@type": "GeoShape",
          box: "-44.0 112.0 -10.0 154.0",
        },
      },
      temporalCoverage: "1825/2026",
      keywords: siteConfig.keywords.join(", "),
      about: siteConfig.searchTopics,
      license: licenseUrl,
      measurementTechnique:
        "Source register review, public metadata review, mapped display-location eligibility, and static frontend export.",
      variableMeasured: [
        {
          "@type": "PropertyValue",
          name: "Public source and provenance",
          description: "Source organisation, source family, source type, URL, publication, and authorship context.",
        },
        {
          "@type": "PropertyValue",
          name: "Narrative classification",
          description: "Archive coding for supernatural humanoid narrative type and source framing.",
        },
        {
          "@type": "PropertyValue",
          name: "Public-text figure label",
          description: "Printed and normalised discovery labels retained with source context.",
        },
        {
          "@type": "PropertyValue",
          name: "Temporal and geographic context",
          description: "Publication date, archive period, state or territory, and reviewed display-location context.",
        },
        {
          "@type": "PropertyValue",
          name: "Publicness and indexing status",
          description: "Public-source eligibility, ethics review, and search-index readiness.",
        },
      ],
      includedInDataCatalog: {
        "@type": "DataCatalog",
        name: siteConfig.siteName,
        url: siteConfig.siteUrl,
      },
      distribution: [
        {
          "@type": "DataDownload",
          name: "AusFigures public frontend data",
          contentUrl: datasetDownloadUrl,
          encodingFormat: "application/json",
          license: licenseUrl,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE.canonicalOrigin),
  applicationName: SITE.name,
  authors: [{ name: siteConfig.creator }],
  creator: siteConfig.creator,
  publisher: siteConfig.creator,
  manifest: "/manifest.webmanifest",
  title: {
    default: `${SITE.name} - ${SITE.fullTitle}`,
    template: `%s | ${SITE.name}`,
  },
  description: siteConfig.shortDescription,
  keywords: [...siteConfig.keywords],
  category: "research",
  referrer: "origin-when-cross-origin",
  alternates: {
    types: {
      "application/rss+xml": absoluteUrl("/feed.xml"),
    },
  },
  openGraph: {
    title: `${SITE.name} - ${SITE.fullTitle}`,
    description: siteConfig.shortDescription,
    url: absoluteUrl(SITE.primaryRoute),
    siteName: SITE.name,
    locale: siteConfig.locale,
    type: "website",
    images: [socialImage],
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE.name} - ${SITE.fullTitle}`,
    description: siteConfig.shortDescription,
    images: [twitterImage],
  },
  appleWebApp: {
    capable: true,
    title: SITE.name,
    statusBarStyle: "black-translucent",
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    icon: [
      { url: SITE.faviconPath, sizes: "any" },
      { url: SITE.iconPath, type: "image/svg+xml" },
      { url: SITE.pngIconPath, sizes: "192x192", type: "image/png" },
    ],
    shortcut: [{ url: SITE.faviconPath }],
    apple: [{ url: SITE.appleIconPath, sizes: "180x180", type: "image/png" }],
  },
  other: {
    "mobile-web-app-capable": "yes",
    "msapplication-TileColor": "#030504",
  },
};

export const viewport: Viewport = {
  colorScheme: "dark light",
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#030504" },
    { media: "(prefers-color-scheme: light)", color: "#d8ccb2" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en-AU" suppressHydrationWarning>
      <head>
        <link
          rel="search"
          type="application/opensearchdescription+xml"
          title={SITE.name}
          href={SITE.openSearchPath}
        />
        <link rel="me" href={SITE.repositoryUrl} />
        <Script
          id="ausfigures-theme-bootstrap"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
try {
  var theme = sessionStorage.getItem("aus-archive-theme");
  if (theme !== "dark" && theme !== "light") {
    theme = "dark";
  }
  document.documentElement.dataset.theme = theme;
} catch (error) {
  document.documentElement.dataset.theme = "dark";
}
            `,
          }}
        />
        <Script
          id="ausfigures-global-structured-data"
          strategy="beforeInteractive"
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(structuredData),
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
