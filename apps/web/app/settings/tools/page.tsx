import { Suspense } from "react";
import { IntegrationsWorkspace } from "@/features/integrations/IntegrationsWorkspace";

export default function SettingsToolsPage() {
  return <Suspense fallback={null}><IntegrationsWorkspace view="tools" /></Suspense>;
}
