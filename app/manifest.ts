import type { MetadataRoute } from "next";
import { SITE, siteConfig } from "@/lib/site";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE.fullTitle,
    short_name: SITE.name,
    description: SITE.description,
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#030504",
    theme_color: "#030504",
    categories: ["education", "reference", "research"],
    lang: siteConfig.locale.replace("_", "-"),
    dir: "ltr",
    shortcuts: [
      {
        name: "Search figures",
        short_name: "Figures",
        description: "Search the AusFigures supernatural humanoid encyclopedia.",
        url: "/figures",
        icons: [{ src: SITE.pngIconPath, sizes: "192x192", type: "image/png" }],
      },
      {
        name: "Explore the public map",
        short_name: "Map",
        description: "Open the schematic public-record map.",
        url: "/map",
        icons: [{ src: SITE.pngIconPath, sizes: "192x192", type: "image/png" }],
      },
      {
        name: "Browse public records",
        short_name: "Records",
        description: "Browse search-ready source-grounded public-text records.",
        url: "/records",
        icons: [{ src: SITE.pngIconPath, sizes: "192x192", type: "image/png" }],
      },
    ],
    icons: [
      {
        src: SITE.iconPath,
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: SITE.pngIconPath,
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: SITE.logoPath,
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: SITE.appleIconPath,
        sizes: "180x180",
        type: "image/png",
        purpose: "any",
      },
    ],
  };
}
