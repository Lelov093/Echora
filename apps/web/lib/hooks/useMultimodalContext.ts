"use client";

import { useCallback, useEffect, useState } from "react";
import {
  checkContextRetention,
  checkParticipantContextVisibility,
  createMultimodalContextEvent,
  expireEphemeralContext,
  getMultimodalContextEvent,
  recordContextPermission,
} from "@/lib/api/multimodalContext";
import type { MultimodalContextEventBundle } from "@/lib/types";

export function useMultimodalContext(contextEventId: string | null) {
  const [data, setData] = useState<MultimodalContextEventBundle | null>(null);
  const [loading, setLoading] = useState(Boolean(contextEventId));
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!contextEventId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getMultimodalContextEvent(contextEventId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load multimodal context");
    } finally {
      setLoading(false);
    }
  }, [contextEventId]);

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
    create: createMultimodalContextEvent,
    recordPermission: recordContextPermission,
    checkVisibility: checkParticipantContextVisibility,
    checkRetention: checkContextRetention,
    expire: expireEphemeralContext,
  };
}
