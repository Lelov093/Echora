"use client";

import { useCallback, useEffect, useState } from "react";
import type { PresenceOpportunity } from "@/lib/api/presence";
import { listOpportunities, acceptOpportunity, dismissOpportunity, snoozeOpportunity, suppressOpportunityType } from "@/lib/api/presence";
import { DEFAULT_COMPANION_ID } from "@/lib/stores/appStore";

export function usePresenceQueue(companionId?: string | null, enabled = true) {
  const scopedCompanionId = companionId === undefined ? DEFAULT_COMPANION_ID : companionId;
  const [items, setItems] = useState<PresenceOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLock, setActionLock] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    if (!enabled) {
      setLoading(true);
      return;
    }
    setLoading(true); setError(null);
    try {
      const params: Record<string, string> = scopedCompanionId
        ? { companion_id: scopedCompanionId, page_size: "50" }
        : { page_size: "50" };
      const data = await listOpportunities(params);
      setItems(data.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load presence data");
    } finally { setLoading(false); }
  }, [enabled, scopedCompanionId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => { load(); }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  async function act(id: string, fn: () => Promise<unknown>) {
    setActionLock(p => ({ ...p, [id]: true }));
    try { await fn(); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
    finally { setActionLock(p => ({ ...p, [id]: false })); }
  }

  return {
    items, loading, error, reload: load, actionLock,
    accept: (id: string) => act(id, () => acceptOpportunity(id)),
    dismiss: (id: string) => act(id, () => dismissOpportunity(id)),
    snooze: (id: string) => act(id, () => snoozeOpportunity(id)),
    suppress: (id: string) => act(id, () => suppressOpportunityType(id)),
  };
}
