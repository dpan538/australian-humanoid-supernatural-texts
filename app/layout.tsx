import type { Metadata, Viewport } from "next";
import { SITE, absoluteUrl, siteConfig, socialImageMetadata } from "@/lib/site";
import "./globals.css";
import "./mobile.css";

const socialImage = socialImageMetadata();
const twitterImage = socialImageMetadata(SITE.twitterImagePath);

const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${siteConfig.siteUrl}/#website`,
      name: siteConfig.siteName,
      alternateName: siteConfig.fullTitle,
      url: siteConfig.siteUrl,
      description: siteConfig.shortDescription,
      inLanguage: "en-AU",
      creator: {
        "@type": "Person",
        name: siteConfig.creator,
      },
      isAccessibleForFree: true,
    },
    {
      "@type": "Dataset",
      "@id": `${siteConfig.siteUrl}/#dataset`,
      name: siteConfig.fullTitle,
      alternateName: siteConfig.siteName,
      url: siteConfig.siteUrl,
      description: siteConfig.shortDescription,
      inLanguage: "en-AU",
      creator: {
        "@type": "Person",
        name: siteConfig.creator,
      },
      isAccessibleForFree: true,
      spatialCoverage: {
        "@type": "Country",
        name: "Australia",
      },
      keywords: siteConfig.keywords.join(", "),
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
    icon: [{ url: "/icon.svg?v=pixel-figure-20260629", type: "image/svg+xml" }],
    apple: [{ url: "/apple-icon?v=pixel-figure-20260629", sizes: "180x180", type: "image/png" }],
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
