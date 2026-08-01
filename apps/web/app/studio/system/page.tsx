import { redirect } from "next/navigation";

export default async function StudioSystemPage({ searchParams }: { searchParams: Promise<{ view?: string }> }) {
  const { view } = await searchParams;
  if (view === "provider") redirect("/settings/system/providers");
  if (view === "permissions") redirect("/settings/tools");
  if (view === "data-privacy") redirect("/settings/system/data-privacy");
  if (view === "diagnostics") redirect("/settings/system/diagnostics");
  if (view === "policy" || view === "reranker" || view === "presence") redirect("/settings/system/shadow-policies");
  redirect("/settings/system/diagnostics");
}
