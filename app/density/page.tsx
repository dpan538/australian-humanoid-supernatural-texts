import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { RouteStructuredData } from "@/components/route-structured-data";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/density");

export default function DensityPage() {
  return (
    <>
      <RouteStructuredData path="/density" />
      <ArchiveTerminalRoute view="density" />
    </>
  );
}
