import { ImageResponse } from "next/og";
import { SITE, siteConfig } from "@/lib/site";

export const alt = `${SITE.name} - ${SITE.fullTitle}`;
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

const pixelRows = [
  "00100",
  "01110",
  "00100",
  "11111",
  "10101",
  "00100",
  "01010",
  "10001",
];

function PixelFigure() {
  return (
    <div
      aria-hidden="true"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      {pixelRows.map((row, rowIndex) => (
        <div
          key={rowIndex}
          style={{
            display: "flex",
            gap: 4,
            height: 22,
          }}
        >
          {[...row].map((cell, columnIndex) => (
            <div
              key={`${rowIndex}-${columnIndex}`}
              style={{
                width: 22,
                height: 22,
                background: cell === "1" ? "#2f6bff" : "transparent",
                boxShadow: cell === "1" ? "0 0 18px rgba(47, 107, 255, 0.55)" : "none",
              }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          background: "#030504",
          color: "#f3f1e8",
          fontFamily: '"Courier New", monospace',
          padding: 52,
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            border: "1px solid rgba(239, 235, 220, 0.34)",
            background:
              "linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.012))",
            padding: 44,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 32,
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 18,
                maxWidth: 760,
              }}
            >
              <div
                style={{
                  color: "#6ee1cb",
                  fontSize: 24,
                  textTransform: "uppercase",
                }}
              >
                Source-grounded public-text archive
              </div>
              <div
                style={{
                  fontSize: 92,
                  lineHeight: 0.92,
                  fontWeight: 700,
                }}
              >
                {SITE.name}
              </div>
              <div
                style={{
                  color: "#d7d2c2",
                  fontSize: 30,
                  lineHeight: 1.28,
                }}
              >
                {SITE.fullTitle}
              </div>
            </div>
            <PixelFigure />
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "space-between",
              gap: 36,
              borderTop: "1px solid rgba(239, 235, 220, 0.22)",
              paddingTop: 28,
            }}
          >
            <div
              style={{
                maxWidth: 780,
                color: "#bfb8a8",
                fontSize: 26,
                lineHeight: 1.32,
              }}
            >
              Map markers are public display locations for records, not proof, habitats, or
              populations.
            </div>
            <div
              style={{
                color: "#2f6bff",
                fontSize: 26,
                whiteSpace: "nowrap",
              }}
            >
              {siteConfig.domain}
            </div>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
