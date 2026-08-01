import { loadArchiveData } from "@/lib/archive-catalog";
import { MOBILE_RECORD_CHUNK_SIZE } from "@/lib/mobile-archive-data";

export const dynamic = "force-static";
export const revalidate = 86400;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  const chunkCount = Math.ceil(data.records.length / MOBILE_RECORD_CHUNK_SIZE);
  return Array.from({ length: chunkCount }, (_, index) => ({ chunk: String(index) }));
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ chunk: string }> },
) {
  const { chunk } = await params;
  const chunkIndex = Number(chunk);
  const data = await loadArchiveData();
  const chunkCount = Math.ceil(data.records.length / MOBILE_RECORD_CHUNK_SIZE);

  if (!Number.isInteger(chunkIndex) || chunkIndex < 0 || chunkIndex >= chunkCount) {
    return Response.json({ error: "Record chunk not found" }, { status: 404 });
  }

  const start = chunkIndex * MOBILE_RECORD_CHUNK_SIZE;
  return Response.json(
    {
      schema_version: "mobile-records/v1",
      generated_at: data.generated_at,
      chunk: chunkIndex,
      chunk_count: chunkCount,
      record_count: data.records.length,
      records: data.records.slice(start, start + MOBILE_RECORD_CHUNK_SIZE),
    },
    {
      headers: {
        "Cache-Control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
      },
    },
  );
}
