import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/");

export default function MapPage() {
  return <ArchiveTerminalRoute view="map" />;
}
