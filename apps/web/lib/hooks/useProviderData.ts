"use client";

import { useCallback } from "react";
import { listFallbackEvents, listLlmCallRecords, listModelConfigs, listPromptVersions, listProviderConfigs } from "@/lib/api/providers";
import { usePaginatedData } from "@/lib/hooks/usePaginatedData";

export function useProviderConfigs(pageSize = 25) {
  const loader = useCallback(() => listProviderConfigs({ page_size: pageSize }), [pageSize]);
  return usePaginatedData(loader);
}

export function useModelConfigs(providerConfigId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listModelConfigs({ provider_config_id: providerConfigId, page_size: pageSize }),
    [providerConfigId, pageSize],
  );
  return usePaginatedData(loader);
}

export function usePromptVersions(promptKey?: string, pageSize = 25) {
  const loader = useCallback(
    () => listPromptVersions({ prompt_key: promptKey, page_size: pageSize }),
    [promptKey, pageSize],
  );
  return usePaginatedData(loader);
}

export function useLlmCalls(traceRunId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listLlmCallRecords({ trace_run_id: traceRunId, page_size: pageSize }),
    [traceRunId, pageSize],
  );
  return usePaginatedData(loader);
}

export function useFallbackEvents(traceRunId?: string, pageSize = 25) {
  const loader = useCallback(
    () => listFallbackEvents({ trace_run_id: traceRunId, page_size: pageSize }),
    [traceRunId, pageSize],
  );
  return usePaginatedData(loader);
}
