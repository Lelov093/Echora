import { Suspense } from "react";
import { QualityWorkspace } from "@/features/quality/QualityWorkspace";

export default function SettingsEvaluationsPage() {
  return <Suspense fallback={null}><QualityWorkspace route="evaluation" /></Suspense>;
}
