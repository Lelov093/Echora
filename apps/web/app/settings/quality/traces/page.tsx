import { Suspense } from "react";
import { QualityWorkspace } from "@/features/quality/QualityWorkspace";

export default function SettingsTracesPage() {
  return <Suspense fallback={null}><QualityWorkspace route="trace" /></Suspense>;
}
