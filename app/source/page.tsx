import { ArchiveTerminal } from "@/components/archive-terminal";
import { frontendData } from "@/lib/frontend-data";

export default function SourcePage() {
  return <ArchiveTerminal data={frontendData} view="source" />;
}
