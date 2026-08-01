"use client";

import { useCallback, useEffect, useState } from "react";
import { getMemoryImpact, type MemoryImpactResponse } from "@/lib/api/memoryImpact";

export function useMemoryImpact(memoryId: string | null) {
  const [data, setData] = useState<MemoryImpactResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!memoryId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getMemoryImpact(memoryId);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load memory impact");
    } finally {
      setLoading(false);
    }
  }, [memoryId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    load();
  }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return { data, loading, error, reload: load };
}
