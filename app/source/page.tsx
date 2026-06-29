import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/source");

export default function SourcePage() {
  return <ArchiveTerminalRoute view="source" />;
}
