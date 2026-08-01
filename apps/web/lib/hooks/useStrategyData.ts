"use client";

import { useCallback } from "react";
import { listMemoryRerankerRuns, listPresencePolicyRuns, listRerankerTrainingExamples } from "@/lib/api/strategy";
import { usePaginatedData } from "@/lib/hooks/usePaginatedData";

export function useRerankerExamples(memoryId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listRerankerTrainingExamples({ memory_id: memoryId, page_size: pageSize }),
    [memoryId, pageSize],
  );
  return usePaginatedData(loader);
}

export function useMemoryRerankerRuns(traceRunId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listMemoryRerankerRuns({ trace_run_id: traceRunId, page_size: pageSize }),
    [traceRunId, pageSize],
  );
  return usePaginatedData(loader);
}

export function usePresencePolicyRuns(traceRunId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listPresencePolicyRuns({ trace_run_id: traceRunId, page_size: pageSize }),
    [traceRunId, pageSize],
  );
  return usePaginatedData(loader);
}
