"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchHub, type HubData } from "@/lib/api/hub";
import { DEFAULT_COMPANION_ID } from "@/lib/stores/appStore";

export function useCompanionHub(companionId?: string | null) {
  const scopedCompanionId = companionId ?? DEFAULT_COMPANION_ID;
  const [data, setData] = useState<HubData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const result = await fetchHub(scopedCompanionId);
      setData(result);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to load hub";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [scopedCompanionId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    load();
  }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return { data, loading, error, reload: load };
}
