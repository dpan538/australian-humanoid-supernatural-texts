import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";
import { SITE, type SocialCardTone } from "@/lib/site";

export const runtime = "edge";

const CARD_SIZE = { width: 1200, height: 630 } as const;

const PALETTES: Record<SocialCardTone, { canvas: string; panel: string; accent: string; ink: string; softInk: string }> = {
  ink: { canvas: "#171714", panel: "#272720", accent: "#d7c570", ink: "#f3eee2", softInk: "#c9c2b3" },
  sage: { canvas: "#1b211c", panel: "#91a78f", accent: "#d9cb72", ink: "#111411", softInk: "#273129" },
  ochre: { canvas: "#201d16", panel: "#d4c17e", accent: "#ab6438", ink: "#171612", softInk: "#3f3a2e" },
  blue: { canvas: "#161d22", panel: "#91b5c7", accent: "#e4cf60", ink: "#111518", softInk: "#2c3b43" },
  clay: { canvas: "#211a17", panel: "#bb8d71", accent: "#dfcf78", ink: "#17120f", softInk: "#403129" },
  paper: { canvas: "#181815", panel: "#eee9dc", accent: "#df7828", ink: "#121310", softInk: "#4e4e46" },
};

export async function GET(request: NextRequest) {
  const parameters = request.nextUrl.searchParams;
  const title = safeText(parameters.get("title"), "Australian Supernatural Humanoid Public-Text Archive", 96);
  const description = safeText(parameters.get("description"), SITE.description, 176);
  const eyebrow = safeText(parameters.get("eyebrow"), "PUBLIC-TEXT ARCHIVE", 38).toUpperCase();
  const metric = safeText(parameters.get("metric"), "", 22);
  const requestedTone = parameters.get("tone");
  const tone: SocialCardTone = isTone(requestedTone) ? requestedTone : "paper";
  const palette = PALETTES[tone];

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: palette.canvas,
          color: palette.ink,
          fontFamily: "Arial, Helvetica, sans-serif",
          padding: 34,
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            borderRadius: 46,
            background: palette.panel,
            padding: "46px 52px 42px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 30 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
              <span
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: 999,
                  background: palette.accent,
                }}
              />
              <span style={{ fontSize: 23, fontWeight: 700, letterSpacing: 2.2 }}>{eyebrow}</span>
            </div>
            <span style={{ fontSize: 24, fontWeight: 700 }}>{SITE.name}</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 22, width: "100%" }}>
            <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 42 }}>
              <div
                style={{
                  display: "flex",
                  maxWidth: metric ? 800 : 1000,
                  fontSize: title.length > 64 ? 56 : 68,
                  lineHeight: 1.02,
                  fontWeight: 700,
                  letterSpacing: -2.4,
                }}
              >
                {title}
              </div>
              {metric ? (
                <div
                  style={{
                    display: "flex",
                    color: palette.accent,
                    fontSize: metric.length > 12 ? 52 : 76,
                    lineHeight: 0.95,
                    fontWeight: 700,
                    letterSpacing: -2.2,
                    whiteSpace: "nowrap",
                  }}
                >
                  {metric}
                </div>
              ) : null}
            </div>
            <div
              style={{
                display: "flex",
                maxWidth: 980,
                color: palette.softInk,
                fontSize: 27,
                lineHeight: 1.28,
              }}
            >
              {description}
            </div>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderTop: `2px solid ${palette.softInk}`,
              paddingTop: 24,
            }}
          >
            <div style={{ display: "flex", gap: 9 }} aria-hidden="true">
              {Array.from({ length: 12 }, (_, index) => (
                <span
                  key={index}
                  style={{
                    width: index % 4 === 0 ? 24 : 11,
                    height: 11,
                    borderRadius: 999,
                    background: index < 8 ? palette.accent : palette.softInk,
                  }}
                />
              ))}
            </div>
            <span style={{ fontSize: 22, fontWeight: 700, letterSpacing: 1.2 }}>{SITE.domain}</span>
          </div>
        </div>
      </div>
    ),
    {
      ...CARD_SIZE,
      headers: {
        "Cache-Control": "public, max-age=86400, s-maxage=604800, stale-while-revalidate=2592000",
      },
    },
  );
}

function safeText(value: string | null, fallback: string, limit: number) {
  const text = (value || fallback).replace(/[<>]/g, "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trimEnd()}…` : text;
}

function isTone(value: string | null): value is SocialCardTone {
  return value !== null && Object.prototype.hasOwnProperty.call(PALETTES, value);
}
