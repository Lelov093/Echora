"use client";

import { useCallback, useMemo } from "react";
import { usePaginatedData } from "./usePaginatedData";
import {
  createDelegatedExecutionIntent,
  createDelegatedSharedExperience,
  getDelegatedExecutionIntent,
  inspectDelegatedExecution,
  linkDelegatedExecution,
  listDelegatedExecutionIntents,
} from "@/lib/api/delegatedExecution";
import type { DelegatedExecutionIntentRecord } from "@/lib/types";

export function useDelegatedExecution(params?: Record<string, string | number | undefined | null>) {
  const paramsKey = JSON.stringify(params ?? {});
  const stableParams = useMemo(
    () => (paramsKey === "{}" ? undefined : (JSON.parse(paramsKey) as Record<string, string | number | undefined | null>)),
    [paramsKey],
  );
  const loadIntents = useCallback(
    () => listDelegatedExecutionIntents(stableParams),
    [stableParams],
  );
  const state = usePaginatedData<DelegatedExecutionIntentRecord>(loadIntents);
  return {
    ...state,
    create: createDelegatedExecutionIntent,
    getById: getDelegatedExecutionIntent,
    link: linkDelegatedExecution,
    inspect: inspectDelegatedExecution,
    createSharedExperience: createDelegatedSharedExperience,
  };
}
