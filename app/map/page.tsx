import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { RouteStructuredData } from "@/components/route-structured-data";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/map");

export default function MapPage() {
  return (
    <>
      <RouteStructuredData path="/map" />
      <ArchiveTerminalRoute view="map" />
    </>
  );
}
