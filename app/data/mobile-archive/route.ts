import { loadArchiveData } from "@/lib/archive-catalog";
import { buildMobileArchiveData } from "@/lib/mobile-archive-data";

export const dynamic = "force-static";
export const revalidate = 86400;

export async function GET() {
  const data = await loadArchiveData();
  return Response.json(buildMobileArchiveData(data), {
    headers: {
      "Cache-Control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
    },
  });
}
