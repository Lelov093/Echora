import { Suspense } from "react";
import { QualityWorkspace } from "@/features/quality/QualityWorkspace";

export default function SettingsReplaysPage() {
  return <Suspense fallback={null}><QualityWorkspace route="replay" /></Suspense>;
}
