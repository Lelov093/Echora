import { Suspense } from "react";
import { SystemWorkspace } from "@/features/system/SystemWorkspace";

export default function SettingsDiagnosticsPage() {
  return <Suspense fallback={null}><SystemWorkspace view="diagnostics" /></Suspense>;
}
