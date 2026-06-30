import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { RouteStructuredData } from "@/components/route-structured-data";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/");

export default function Home() {
  return (
    <>
      <RouteStructuredData path="/" />
      <ArchiveTerminalRoute view="map" />
    </>
  );
}
