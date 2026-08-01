"use client";

import { useEffect } from "react";
import { useUIStore } from "@/lib/stores/appStore";

export function CompanionSettingsScope({ companionId, children }: { companionId: string; children: React.ReactNode }) {
  const activeCompanionId = useUIStore((state) => state.activeCompanionId);
  const setActiveCompanionId = useUIStore((state) => state.setActiveCompanionId);

  useEffect(() => {
    if (activeCompanionId !== companionId) setActiveCompanionId(companionId);
  }, [activeCompanionId, companionId, setActiveCompanionId]);

  return <>{children}</>;
}
