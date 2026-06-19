import { ArchiveTerminal } from "@/components/archive-terminal";
import { frontendData } from "@/lib/frontend-data";

export default function MapPage() {
  return <ArchiveTerminal data={frontendData} view="map" />;
}
