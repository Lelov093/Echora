"use client";

import { useCallback, useEffect, useState } from "react";
import {
  appendRealtimeMemoryBufferItem,
  createRealtimeMemoryBuffer,
  createRealtimeSharedMemoryCandidate,
  detectRealtimeSalientMoment,
  expireRealtimeMemoryBufferItems,
  getRealtimeMemoryBuffer,
  getRealtimeSalientMoment,
  writeRealtimeMemoryGateTrace,
} from "@/lib/api/realtimeMemory";
import type { RealtimeMemoryBufferBundle } from "@/lib/types";

export function useRealtimeMemory(bufferId: string | null) {
  const [data, setData] = useState<RealtimeMemoryBufferBundle | null>(null);
  const [loading, setLoading] = useState(Boolean(bufferId));
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!bufferId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getRealtimeMemoryBuffer(bufferId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load realtime memory buffer");
    } finally {
      setLoading(false);
    }
  }, [bufferId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    load();
  }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return {
    data,
    loading,
    error,
    reload: load,
    create: createRealtimeMemoryBuffer,
    appendItem: appendRealtimeMemoryBufferItem,
    expireItems: expireRealtimeMemoryBufferItems,
    writeGateTrace: writeRealtimeMemoryGateTrace,
    detectSalientMoment: detectRealtimeSalientMoment,
    getSalientMoment: getRealtimeSalientMoment,
    createSharedMemoryCandidate: createRealtimeSharedMemoryCandidate,
  };
}
