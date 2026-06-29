# AusFigures Domain Setup

Production canonical domain:

https://ausfigures.com

## Canonical Policy

- Apex domain `ausfigures.com` is canonical.
- `www.ausfigures.com` should redirect to `ausfigures.com`.
- Vercel preview URLs are not canonical and must remain preview-only.
- README, metadata, sitemap, robots, and llms.txt should use the apex canonical domain.

## Vercel Project Settings

1. Import the GitHub repository into Vercel.
2. Confirm Framework Preset is `Next.js`.
3. Confirm Production Branch is `main`.
4. Confirm Root Directory is the repository root.
5. Confirm Install Command is `npm ci`.
6. Confirm Build Command is `npm run build`.
7. Leave Output Directory blank/default for the Next.js framework preset.
8. Deploy the project and use the temporary `*.vercel.app` URL only as a preview deployment.

## Domains

1. In Vercel Project Settings, open Domains.
2. Add `ausfigures.com`.
3. Add `www.ausfigures.com` if using the www redirect.
4. Use `ausfigures.com` as the canonical production domain.
5. Redirect `www.ausfigures.com` to `ausfigures.com`.

## DNS

Configure DNS records exactly as Vercel shows in Project Settings -> Domains or via `vercel domains inspect`.

Typical Vercel patterns are:

- Apex domain such as `ausfigures.com`: A record.
- Subdomain such as `www.ausfigures.com`: CNAME record.

Do not copy these typical patterns blindly. Add exactly the records Vercel shows after the domain is added to the project.

## Post-Deploy Checks

1. `https://ausfigures.com/` returns 200 and renders the index map.
2. `https://ausfigures.com/robots.txt` returns 200 and references `https://ausfigures.com/sitemap.xml`.
3. `https://ausfigures.com/sitemap.xml` returns 200 and only lists `ausfigures.com` URLs.
4. `https://ausfigures.com/llms.txt` returns 200.
5. `https://ausfigures.com/opengraph-image` returns 200 image/png.
6. `https://ausfigures.com/twitter-image` returns 200 image/png.
7. `https://ausfigures.com/manifest.webmanifest` returns browser identity metadata for Chrome.
8. `https://ausfigures.com/apple-icon` returns 200 image/png for Safari and Apple surfaces.
9. `https://www.ausfigures.com/` redirects to `https://ausfigures.com/`.
10. No canonical, Open Graph, sitemap, robots, llms.txt, README deployment badge, or README production URL points to `*.vercel.app`.

## Optional CLI Checks

If Vercel CLI is available and authenticated, these read-only checks can help inspect setup:

```sh
vercel domains inspect ausfigures.com
vercel domains inspect www.ausfigures.com
vercel certs ls
vercel curl /
```

Do not run Vercel CLI commands that modify project settings unless explicitly authorized.
