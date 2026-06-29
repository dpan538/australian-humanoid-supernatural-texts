import { ArchiveTerminalRoute } from "@/components/archive-terminal";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/dashboard");

export default function DashboardPage() {
  return <ArchiveTerminalRoute view="dashboard" />;
}
