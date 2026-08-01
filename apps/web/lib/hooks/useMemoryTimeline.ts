"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getMemoryTimelineForMemory,
  listMemoryUsageEvents,
  listMemoryLifecycleEvents,
  type TimelineEvent,
  type UsageEvent,
  type LifecycleEvent,
} from "@/lib/api/memoryTimeline";

export interface MemoryTimelineData {
  timeline: TimelineEvent[];
  usage: UsageEvent[];
  lifecycle: LifecycleEvent[];
}

export function useMemoryTimeline(memoryId: string | null | undefined) {
  const [data, setData] = useState<MemoryTimelineData | null>(null);
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
      const [timelineRes, usageRes, lifecycleRes] = await Promise.all([
        getMemoryTimelineForMemory(memoryId).catch(() => ({ items: [], total: 0 })),
        listMemoryUsageEvents(memoryId).catch(() => ({ items: [], total: 0 })),
        listMemoryLifecycleEvents(memoryId).catch(() => ({ items: [], total: 0 })),
      ]);
      setData({
        timeline: timelineRes.items || [],
        usage: usageRes.items || [],
        lifecycle: lifecycleRes.items || [],
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load memory timeline");
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
