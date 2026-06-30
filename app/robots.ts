import type { MetadataRoute } from "next";
import { SITE } from "@/lib/site";

const allowedCrawlers = [
  "*",
  "Googlebot",
  "Googlebot-Image",
  "Google-Extended",
  "Bingbot",
  "Baiduspider",
  "YandexBot",
  "DuckDuckBot",
  "Applebot",
  "Applebot-Extended",
  "Slurp",
  "Sogou web spider",
  "Exabot",
  "SeznamBot",
  "NaverBot",
  "GPTBot",
  "ChatGPT-User",
  "OAI-SearchBot",
  "ClaudeBot",
  "Claude-SearchBot",
  "PerplexityBot",
  "Perplexity-User",
  "CCBot",
  "anthropic-ai",
] as const;

export default function robots(): MetadataRoute.Robots {
  return {
    rules: allowedCrawlers.map((userAgent) => ({
      userAgent,
      allow: "/",
    })),
    sitemap: `${SITE.url}/sitemap.xml`,
  };
}
