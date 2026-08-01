"use client";

import { useCallback, useEffect, useState } from "react";
import { getRealtimeTrace } from "@/lib/api/realtimeTrace";
import type { RealtimeTraceV5Detail } from "@/lib/types";

export function useRealtimeTrace(traceRunId: string | null) {
  const [data, setData] = useState<RealtimeTraceV5Detail | null>(null);
  const [loading, setLoading] = useState(Boolean(traceRunId));
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!traceRunId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getRealtimeTrace(traceRunId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load realtime trace");
    } finally {
      setLoading(false);
    }
  }, [traceRunId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    load();
  }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return { data, loading, error, reload: load };
}
