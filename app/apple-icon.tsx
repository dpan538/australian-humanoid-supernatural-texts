import { ImageResponse } from "next/og";

export const size = {
  width: 180,
  height: 180,
};
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#030504",
        }}
      >
        <svg width="156" height="156" viewBox="0 0 64 64" shapeRendering="crispEdges">
          <rect width="64" height="64" fill="#030504" />
          <rect x="3" y="3" width="58" height="58" fill="none" stroke="#31413f" strokeWidth="2" />
          <path d="M10 49h44" stroke="#163a38" strokeWidth="2" />
          <path d="M14 49h19" stroke="#78e4dc" strokeWidth="2" />
          <path d="M38 49h12" stroke="#2f6bff" strokeWidth="2" />
          <rect x="11" y="47" width="4" height="4" fill="#78e4dc" />
          <rect x="49" y="47" width="4" height="4" fill="#2f6bff" />
          <g transform="translate(8 2) scale(3)" fill="#2f6bff">
            <rect x="6" y="1" width="4" height="4" />
            <rect x="5" y="5" width="6" height="5" />
            <rect x="3" y="6" width="2" height="4" />
            <rect x="11" y="6" width="2" height="4" />
            <rect x="5" y="10" width="2" height="5" />
            <rect x="9" y="10" width="2" height="5" />
            <rect x="4" y="14" width="3" height="1" />
            <rect x="9" y="14" width="3" height="1" />
          </g>
          <g transform="translate(8 2) scale(3)" fill="#78e4dc" opacity="0.8">
            <rect x="6" y="1" width="1" height="1" />
            <rect x="5" y="5" width="1" height="1" />
            <rect x="3" y="6" width="1" height="1" />
          </g>
        </svg>
      </div>
    ),
    size,
  );
}
