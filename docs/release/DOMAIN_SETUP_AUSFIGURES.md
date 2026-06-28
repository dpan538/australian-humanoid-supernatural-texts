# Domain Setup For AusFigures

Target domain: `ausfigures.com`

## Vercel Project

1. Import the GitHub repository into Vercel.
2. Confirm Framework Preset is `Next.js`.
3. Confirm Production Branch is `main`.
4. Confirm Root Directory is the repository root.
5. Confirm Install Command is `npm install`.
6. Confirm Build Command is `npm run build`.
7. Confirm Output Directory is `.next`.
8. Deploy the project and open the temporary `*.vercel.app` URL.

## Domains

1. In Vercel Project Settings, open Domains.
2. Add `ausfigures.com`.
3. Add `www.ausfigures.com`.
4. Use `ausfigures.com` as the canonical domain.
5. Redirect `www.ausfigures.com` to `ausfigures.com`.

## Namecheap DNS

Use the DNS records shown in the Vercel UI as the source of truth.

Typical Vercel patterns are:

- Apex domain such as `ausfigures.com`: A record.
- Subdomain such as `www.ausfigures.com`: CNAME record.

Do not copy these typical patterns blindly. Add exactly the records Vercel shows
after the domain is added to the project.

## Verification

1. Wait for DNS propagation.
2. Confirm Vercel domain status is valid.
3. Confirm HTTPS certificate is active.
4. Open `https://ausfigures.com/about`.
5. Open `https://ausfigures.com/map`.
6. Open `https://www.ausfigures.com` and confirm it redirects to the canonical domain.
