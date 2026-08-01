"use client";

import { useCallback } from "react";
import { listToolDefinitions, listToolRuns } from "@/lib/api/tools";
import { usePaginatedData } from "@/lib/hooks/usePaginatedData";
import { useActiveCompanionContext } from "@/lib/hooks/useActiveCompanion";

export function useToolDefinitions(pageSize = 25) {
  const loader = useCallback(() => listToolDefinitions({ page_size: pageSize }), [pageSize]);
  return usePaginatedData(loader);
}

export function useToolRuns(pageSize = 25) {
  const companion = useActiveCompanionContext();
  const loader = useCallback(
    () => listToolRuns({ companion_id: companion.activeCompanionId, page_size: pageSize }),
    [companion.activeCompanionId, pageSize],
  );
  return usePaginatedData(loader);
}
