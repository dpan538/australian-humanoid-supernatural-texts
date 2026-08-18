import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [
          {
            type: "host",
            value: "www.ausfigures.com",
          },
        ],
        destination: "https://ausfigures.com/:path*",
        permanent: true,
      },
      {
        source: "/topics",
        destination: "/figures",
        permanent: true,
      },
      {
        source: "/map",
        destination: "/",
        permanent: true,
      },
      {
        source: "/sources",
        destination: "/source",
        permanent: true,
      },
      {
        source: "/sources/:path*",
        destination: "/source",
        permanent: true,
      },
      {
        source: "/topics/australian-supernatural",
        destination: "/figures",
        permanent: true,
      },
      {
        source: "/topics/supernatural-humanoids",
        destination: "/figures",
        permanent: true,
      },
      {
        source: "/topics/yowie-records",
        destination: "/figures/yowie",
        permanent: true,
      },
      {
        source: "/topics/bunyip-public-texts",
        destination: "/figures/bunyip",
        permanent: true,
      },
      {
        source: "/topics/australian-ghosts-apparitions",
        destination: "/figures/ghost",
        permanent: true,
      },
      {
        source: "/topics/spirit-person-narratives",
        destination: "/figures/spirit",
        permanent: true,
      },
      {
        source: "/topics/:path*",
        destination: "/figures",
        permanent: true,
      },
      {
        source: "/labels",
        destination: "/figures",
        permanent: true,
      },
      {
        source: "/labels/spirits",
        destination: "/figures/spirit",
        permanent: true,
      },
      {
        source: "/labels/ghosts",
        destination: "/figures/ghost",
        permanent: true,
      },
      {
        source: "/labels/apparition",
        destination: "/figures/ghost",
        permanent: true,
      },
      {
        source: "/labels/:slug",
        destination: "/figures/:slug",
        permanent: true,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/data/frontend-interactive.json",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=0, s-maxage=86400, stale-while-revalidate=604800",
          },
        ],
      },
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
