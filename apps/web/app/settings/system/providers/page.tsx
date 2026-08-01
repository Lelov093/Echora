import { Suspense } from "react";
import { SystemWorkspace } from "@/features/system/SystemWorkspace";

export default function SettingsProvidersPage() {
  return <Suspense fallback={null}><SystemWorkspace view="provider" /></Suspense>;
}
