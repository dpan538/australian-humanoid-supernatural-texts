import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/density");

export default function DensityPage() {
  return <ArchiveTerminalRoute view="density" />;
}
