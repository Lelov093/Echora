"use client";

import { useCallback, useEffect, useState } from "react";
import {
  listFeedbackEvents,
  createFeedbackEvent,
  type FeedbackEvent,
} from "@/lib/api/feedback";

export function useFeedbackEvents(params?: Record<string, string>) {
  const [data, setData] = useState<FeedbackEvent[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const paramKey = params ? JSON.stringify(params) : "";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listFeedbackEvents(params);
      setData(result.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load feedback events");
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramKey]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    load();
  }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return { data, loading, error, reload: load };
}

export function useCreateFeedbackEvent() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = useCallback(async (payload: Record<string, unknown>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await createFeedbackEvent(payload);
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to create feedback event";
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { create, loading, error };
}
