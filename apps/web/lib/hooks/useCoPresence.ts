"use client";

import { useCallback, useMemo } from "react";
import { usePaginatedData } from "./usePaginatedData";
import {
  addCoPresenceParticipant,
  createCoPresenceSession,
  endCoPresenceSession,
  getCoPresenceSession,
  listCoPresenceSessions,
  patchCoPresenceParticipant,
  patchCoPresenceSession,
} from "@/lib/api/coPresence";
import type { CoPresenceSessionBundle } from "@/lib/types";

export function useCoPresence(params?: Record<string, string | number | undefined | null>) {
  const paramsKey = JSON.stringify(params ?? {});
  const stableParams = useMemo(
    () => (paramsKey === "{}" ? undefined : (JSON.parse(paramsKey) as Record<string, string | number | undefined | null>)),
    [paramsKey],
  );
  const loadSessions = useCallback(
    () => listCoPresenceSessions(stableParams),
    [stableParams],
  );
  const state = usePaginatedData<CoPresenceSessionBundle>(loadSessions);
  return {
    ...state,
    create: createCoPresenceSession,
    getById: getCoPresenceSession,
    patch: patchCoPresenceSession,
    addParticipant: addCoPresenceParticipant,
    patchParticipant: patchCoPresenceParticipant,
    end: endCoPresenceSession,
  };
}
