import { Suspense } from "react";
import { SystemWorkspace } from "@/features/system/SystemWorkspace";

export default function DataPrivacySettingsPage() {
  return <Suspense fallback={null}><SystemWorkspace view="data-privacy" /></Suspense>;
}
