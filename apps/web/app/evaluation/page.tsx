import { redirect } from "next/navigation";

export default async function EvaluationPage({ searchParams }: { searchParams: Promise<{ view?: string }> }) {
  const { view } = await searchParams;
  redirect(view === "regression" ? "/settings/quality/regressions" : "/settings/quality/evaluations");
}
