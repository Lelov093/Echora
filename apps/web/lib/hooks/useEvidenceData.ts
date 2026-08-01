"use client";

import { useCallback } from "react";
import { listEvidenceSufficiencyEvents, listGrowthConsistencyChecks, listOutdatedMemoryFlags } from "@/lib/api/evidence";
import { usePaginatedData } from "@/lib/hooks/usePaginatedData";

export function useEvidenceEvents(traceRunId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listEvidenceSufficiencyEvents({ trace_run_id: traceRunId, page_size: pageSize }),
    [traceRunId, pageSize],
  );
  return usePaginatedData(loader);
}

export function useGrowthConsistencyChecks(traceRunId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listGrowthConsistencyChecks({ trace_run_id: traceRunId, page_size: pageSize }),
    [traceRunId, pageSize],
  );
  return usePaginatedData(loader);
}

export function useOutdatedMemoryFlags(memoryId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listOutdatedMemoryFlags({ memory_id: memoryId, page_size: pageSize }),
    [memoryId, pageSize],
  );
  return usePaginatedData(loader);
}
