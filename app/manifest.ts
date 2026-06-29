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
        src: "/icon.svg?v=pixel-figure-20260629",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/apple-icon?v=pixel-figure-20260629",
        sizes: "180x180",
        type: "image/png",
        purpose: "any",
      },
    ],
  };
}
