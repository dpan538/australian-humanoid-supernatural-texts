import { RecordsIndexPage } from "@/app/records/_components/records-index-page";
import { archivePageMetadata } from "@/lib/archive-metadata";

export const metadata = archivePageMetadata({
  title: "Australian Supernatural Humanoid Public-Text Records",
  description:
    "Browse public-text records in AusFigures across supernatural humanoid narratives, apparitions, spirit-person accounts, giants, legends, encounters, and retellings.",
  path: "/records",
  index: false,
  keywords: ["Australian supernatural records", "public-text record archive", "supernatural humanoid archive"],
});

export default function RecordsPage() {
  return <RecordsIndexPage page={1} />;
}
