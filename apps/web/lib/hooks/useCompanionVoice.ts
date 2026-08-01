"use client";

import { useCallback, useMemo } from "react";
import { usePaginatedData } from "./usePaginatedData";
import {
  createCompanionVoiceSession,
  decideTurnTaking,
  getCompanionVoiceSession,
  listCompanionVoiceSessions,
  recordSttFinal,
  recordSttPartial,
  recordTtsEvent,
  recordVoiceInterruption,
  runVoicePersonaGuard,
} from "@/lib/api/companionVoice";
import type { QueryParams } from "@/lib/api/client";
import type { CompanionVoiceSessionBundle } from "@/lib/types";

export function useCompanionVoice(params?: QueryParams) {
  const paramsKey = JSON.stringify(params ?? {});
  const stableParams = useMemo(() => (paramsKey === "{}" ? undefined : (JSON.parse(paramsKey) as QueryParams)), [paramsKey]);
  const loadSessions = useCallback(() => listCompanionVoiceSessions(stableParams), [stableParams]);
  const state = usePaginatedData<CompanionVoiceSessionBundle>(loadSessions);

  return {
    ...state,
    create: createCompanionVoiceSession,
    getById: getCompanionVoiceSession,
    recordSttPartial,
    recordSttFinal,
    recordTtsEvent,
    decideTurnTaking,
    recordInterruption: recordVoiceInterruption,
    runPersonaGuard: runVoicePersonaGuard,
  };
}
