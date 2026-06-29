import { redirect } from "next/navigation";
import { metadataForRoute } from "@/lib/site";

export const metadata = metadataForRoute("/dashboard");

export default function Home() {
  redirect("/dashboard");
}
