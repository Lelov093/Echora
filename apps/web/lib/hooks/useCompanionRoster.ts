"use client";

import { useCallback } from "react";
import { usePaginatedData } from "./usePaginatedData";
import { createCompanion, getCompanion, listCompanions, updateCompanion } from "@/lib/api/companions";
import type { CompanionBundle } from "@/lib/types";

export function useCompanionRoster(userId?: string | null, scope = "product") {
  const loadRoster = useCallback(
    () => listCompanions({ ...(userId ? { user_id: userId } : {}), scope, page_size: 100 }),
    [scope, userId],
  );
  const state = usePaginatedData<CompanionBundle>(
    loadRoster,
  );

  return {
    ...state,
    create: (data: Record<string, unknown>) => createCompanion(data),
    getById: (companionId: string) => getCompanion(companionId),
    update: (companionId: string, data: Record<string, unknown>) => updateCompanion(companionId, data),
  };
}
