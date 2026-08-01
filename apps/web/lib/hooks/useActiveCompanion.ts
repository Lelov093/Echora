"use client";

import { useEffect, useMemo } from "react";
import { ALL_COMPANIONS_ID, DEFAULT_COMPANION_ID, useUIStore } from "@/lib/stores/appStore";
import { useCompanionRoster } from "@/lib/hooks/useCompanionRoster";

export function useActiveCompanionContext() {
  const roster = useCompanionRoster();
  const activeCompanionId = useUIStore((state) => state.activeCompanionId);
  const hydrated = useUIStore((state) => state.hydrated);
  const setActiveCompanionId = useUIStore((state) => state.setActiveCompanionId);

  const rosterFallbackId = roster.items[0]?.id ?? null;
  const allCompanions = activeCompanionId === ALL_COMPANIONS_ID;
  const effectiveCompanionId = allCompanions ? null : activeCompanionId ?? rosterFallbackId ?? DEFAULT_COMPANION_ID;
  const activeCompanion = useMemo(
    () =>
      effectiveCompanionId
        ? roster.items.find((item) => item.id === effectiveCompanionId) ?? roster.items[0] ?? null
        : null,
    [effectiveCompanionId, roster.items],
  );

  useEffect(() => {
    if (hydrated && !activeCompanionId && rosterFallbackId) {
      setActiveCompanionId(rosterFallbackId);
    }
  }, [activeCompanionId, hydrated, rosterFallbackId, setActiveCompanionId]);

  const resolvedCompanionId = activeCompanion?.id ?? effectiveCompanionId ?? DEFAULT_COMPANION_ID;

  return {
    companions: roster.items,
    loading: roster.loading,
    error: roster.error,
    reload: roster.reload,
    hydrated,
    allCompanions,
    activeCompanion,
    activeCompanionId: resolvedCompanionId,
    companionFilterId: allCompanions ? null : resolvedCompanionId,
    selectedCompanionValue: allCompanions ? ALL_COMPANIONS_ID : resolvedCompanionId,
    setActiveCompanionId,
  };
}
