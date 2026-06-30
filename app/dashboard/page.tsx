import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { RouteStructuredData } from "@/components/route-structured-data";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/dashboard");

export default function DashboardPage() {
  return (
    <>
      <RouteStructuredData path="/dashboard" />
      <ArchiveTerminalRoute view="dashboard" />
    </>
  );
}
