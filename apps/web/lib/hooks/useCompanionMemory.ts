"use client";

import { useCallback, useMemo } from "react";
import { usePaginatedData } from "./usePaginatedData";
import { listCompanionMemories, type CompanionMemoryQuery } from "@/lib/api/companionMemory";
import type { CompanionMemoryRecord } from "@/lib/types";

export function useCompanionMemory(companionId: string | null, params?: CompanionMemoryQuery) {
  const paramsKey = JSON.stringify(params ?? {});
  const stableParams = useMemo(
    () => (paramsKey === "{}" ? undefined : (JSON.parse(paramsKey) as CompanionMemoryQuery)),
    [paramsKey],
  );
  const loadCompanionMemories = useCallback(
    () => (companionId ? listCompanionMemories(companionId, stableParams) : Promise.resolve({ items: [] })),
    [companionId, stableParams],
  );
  return usePaginatedData<CompanionMemoryRecord>(
    loadCompanionMemories,
    { enabled: Boolean(companionId) },
  );
}
