import { Suspense } from "react";
import { QualityWorkspace } from "@/features/quality/QualityWorkspace";

export default function SettingsRegressionsPage() {
  return <Suspense fallback={null}><QualityWorkspace route="regression" /></Suspense>;
}
