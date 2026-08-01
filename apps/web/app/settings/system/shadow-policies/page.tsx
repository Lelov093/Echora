import { Suspense } from "react";
import { SystemWorkspace } from "@/features/system/SystemWorkspace";

export default function SettingsShadowPoliciesPage() {
  return <Suspense fallback={null}><SystemWorkspace view="policy" /></Suspense>;
}
