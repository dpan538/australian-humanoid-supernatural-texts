import { ArchiveTerminal } from "@/components/archive-terminal";
import { frontendData } from "@/lib/frontend-data";

export default function DashboardPage() {
  return <ArchiveTerminal data={frontendData} view="dashboard" />;
}
