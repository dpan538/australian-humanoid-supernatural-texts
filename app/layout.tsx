import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://ausfigures.com"),
  title: {
    default: "AusFigures | Public Text Archive",
    template: "%s | AusFigures",
  },
  description: "A typed public-text archive and research display for Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings.",
  openGraph: {
    title: "AusFigures | Public Text Archive",
    description: "A typed public-text archive and research display for Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings.",
    url: "https://ausfigures.com",
    siteName: "AusFigures",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "AusFigures | Public Text Archive",
    description: "A typed public-text archive and research display for Australian supernatural humanoid narratives, encounters, apparitions, legends, and retellings.",
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
  var theme = localStorage.getItem("aus-archive-theme");
  if (theme !== "dark" && theme !== "light") {
    theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  document.documentElement.dataset.theme = theme;
} catch (error) {
  document.documentElement.dataset.theme = "dark";
}
            `,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
