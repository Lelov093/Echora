"use client";

import { useCallback, useMemo } from "react";
import { usePaginatedData } from "./usePaginatedData";
import {
  addRealtimeParticipant,
  createRealtimeCoPresenceSession,
  endRealtimeCoPresenceSession,
  getRealtimeCoPresenceSession,
  listRealtimeCoPresenceSessions,
  listRealtimeSessionChannels,
  patchRealtimeParticipant,
  patchRealtimeSessionChannel,
  pauseRealtimeCoPresenceSession,
  resumeRealtimeCoPresenceSession,
} from "@/lib/api/realtimeCoPresence";
import type { QueryParams } from "@/lib/api/client";
import type { RealtimeCoPresenceSessionBundle } from "@/lib/types";

export function useRealtimeCoPresence(params?: QueryParams) {
  const paramsKey = JSON.stringify(params ?? {});
  const stableParams = useMemo(() => (paramsKey === "{}" ? undefined : (JSON.parse(paramsKey) as QueryParams)), [paramsKey]);
  const loadSessions = useCallback(() => listRealtimeCoPresenceSessions(stableParams), [stableParams]);
  const state = usePaginatedData<RealtimeCoPresenceSessionBundle>(loadSessions);

  return {
    ...state,
    create: createRealtimeCoPresenceSession,
    getById: getRealtimeCoPresenceSession,
    pause: pauseRealtimeCoPresenceSession,
    resume: resumeRealtimeCoPresenceSession,
    end: endRealtimeCoPresenceSession,
    addParticipant: addRealtimeParticipant,
    patchParticipant: patchRealtimeParticipant,
    listChannels: listRealtimeSessionChannels,
    patchChannel: patchRealtimeSessionChannel,
  };
}
