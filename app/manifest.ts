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
