import type { Metadata } from "next";
import { SITE, absoluteUrl, siteConfig } from "@/lib/site";
import "./globals.css";

const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
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
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE.canonicalOrigin),
  applicationName: SITE.name,
  authors: [{ name: siteConfig.creator }],
  creator: siteConfig.creator,
  publisher: siteConfig.creator,
  title: {
    default: `${SITE.name} - ${SITE.fullTitle}`,
    template: `%s | ${SITE.name}`,
  },
  description: siteConfig.shortDescription,
  alternates: {
    canonical: absoluteUrl(SITE.primaryRoute),
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: `${SITE.name} - ${SITE.fullTitle}`,
    description: siteConfig.shortDescription,
    url: absoluteUrl(SITE.primaryRoute),
    siteName: SITE.name,
    locale: siteConfig.locale,
    type: "website",
  },
  twitter: {
    card: "summary",
    title: `${SITE.name} - ${SITE.fullTitle}`,
    description: siteConfig.shortDescription,
  },
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
            __html: JSON.stringify(websiteJsonLd),
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
