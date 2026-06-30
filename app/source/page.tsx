import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { RouteStructuredData } from "@/components/route-structured-data";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/source");

export default function SourcePage() {
  return (
    <>
      <RouteStructuredData path="/source" />
      <ArchiveTerminalRoute view="source" />
    </>
  );
}
