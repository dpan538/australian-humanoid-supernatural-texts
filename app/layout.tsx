import type { Metadata, Viewport } from "next";
import { SITE, absoluteUrl, siteConfig, socialImageMetadata } from "@/lib/site";
import { seoTopics, topicUrl } from "@/lib/seo-topics";
import "./globals.css";
import "./mobile.css";

const socialImage = socialImageMetadata();
const twitterImage = socialImageMetadata(SITE.twitterImagePath);
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
      publisher: {
        "@id": `${siteConfig.siteUrl}/#organization`,
      },
      creator: {
        "@type": "Person",
        name: siteConfig.creator,
      },
      isAccessibleForFree: true,
      hasPart: seoTopics.map((topic) => ({
        "@type": "CollectionPage",
        name: topic.title,
        url: topicUrl(topic.slug),
        about: topic.queryTerms,
      })),
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
    images: [twitterImage.url],
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
    { media: "(prefers-color-scheme: light)", color: "#f7f4ec" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
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
        <script
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
