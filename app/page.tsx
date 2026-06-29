import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/");

export default function Home() {
  return <ArchiveTerminalRoute view="map" />;
}
