import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RecordsIndexPage } from "@/app/records/_components/records-index-page";
import { loadArchiveData, recordsIndexPageCount } from "@/lib/archive-catalog";
import { archivePageMetadata } from "@/lib/archive-metadata";
import { recordsPagePath } from "@/lib/archive-routing";

type RecordsPaginationPageProps = {
  params: Promise<{ page: string }>;
};

export const dynamicParams = false;

export async function generateStaticParams() {
  const data = await loadArchiveData();
  const pageCount = recordsIndexPageCount(data);
  return Array.from({ length: Math.max(0, pageCount - 1) }, (_, index) => ({
    page: String(index + 2),
  }));
}

export async function generateMetadata({ params }: RecordsPaginationPageProps): Promise<Metadata> {
  const { page: pageParam } = await params;
  const page = Number(pageParam);
  return archivePageMetadata({
    title: `Australian Supernatural Humanoid Public-Text Records — Page ${page}`,
    description: `Browse page ${page} of the search-ready AusFigures public-text record index.`,
    path: recordsPagePath(page),
    index: false,
  });
}

export default async function RecordsPaginationPage({ params }: RecordsPaginationPageProps) {
  const { page: pageParam } = await params;
  const data = await loadArchiveData();
  const page = Number(pageParam);
  const pageCount = recordsIndexPageCount(data);
  if (!Number.isInteger(page) || page < 2 || page > pageCount) {
    notFound();
  }
  return <RecordsIndexPage page={page} />;
}
