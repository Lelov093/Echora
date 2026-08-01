"use client";

import { useCallback } from "react";
import { listFileContextUsages, listFileDocuments, listFileSources } from "@/lib/api/files";
import { usePaginatedData } from "@/lib/hooks/usePaginatedData";

export function useFileSources(pageSize = 25) {
  const loader = useCallback(() => listFileSources({ page_size: pageSize }), [pageSize]);
  return usePaginatedData(loader);
}

export function useFileDocuments(pageSize = 25) {
  const loader = useCallback(() => listFileDocuments({ page_size: pageSize }), [pageSize]);
  return usePaginatedData(loader);
}

export function useFileContextUsages(traceRunId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listFileContextUsages({ trace_run_id: traceRunId, page_size: pageSize }),
    [traceRunId, pageSize],
  );
  return usePaginatedData(loader);
}
