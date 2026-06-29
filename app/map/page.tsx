import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/map");

export default function MapPage() {
  return <ArchiveTerminalRoute view="map" />;
}
