import { Suspense } from "react";
import { QualityWorkspace } from "@/features/quality/QualityWorkspace";

export default function SettingsBadCasesPage() {
  return <Suspense fallback={null}><QualityWorkspace route="bad-cases" /></Suspense>;
}
