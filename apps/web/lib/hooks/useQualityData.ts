"use client";

import { useCallback } from "react";
import { listBadCaseInboxItems } from "@/lib/api/badCaseInbox";
import { listEvaluationDatasets, listEvaluationResults, listEvaluationRuns } from "@/lib/api/evaluation";
import { listRegressionCases, listRegressionResults, listRegressionRuns } from "@/lib/api/regression";
import { listReplays } from "@/lib/api/replays";
import { usePaginatedData } from "@/lib/hooks/usePaginatedData";

export function useReplays(traceRunId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listReplays({ trace_run_id: traceRunId, page_size: pageSize }),
    [traceRunId, pageSize],
  );
  return usePaginatedData(loader);
}

export function useBadCaseInbox(status?: string, pageSize = 25) {
  const loader = useCallback(
    () => listBadCaseInboxItems({ status, page_size: pageSize }),
    [status, pageSize],
  );
  return usePaginatedData(loader);
}

export function useEvaluationLab(pageSize = 25) {
  const datasets = usePaginatedData(useCallback(() => listEvaluationDatasets({ page_size: pageSize }), [pageSize]));
  const runs = usePaginatedData(useCallback(() => listEvaluationRuns({ page_size: pageSize }), [pageSize]));
  const results = usePaginatedData(useCallback(() => listEvaluationResults({ page_size: pageSize }), [pageSize]));
  return { datasets, runs, results };
}

export function useRegressionLab(pageSize = 25) {
  const cases = usePaginatedData(useCallback(() => listRegressionCases({ page_size: pageSize }), [pageSize]));
  const runs = usePaginatedData(useCallback(() => listRegressionRuns({ page_size: pageSize }), [pageSize]));
  const results = usePaginatedData(useCallback(() => listRegressionResults({ page_size: pageSize }), [pageSize]));
  return { cases, runs, results };
}
