"use client";

import { useCallback, useEffect, useState } from "react";
import { listGrowthCandidates, commitGrowth, editGrowthCandidate, rejectGrowth, listGrowthRecords, revertGrowthRecord } from "@/lib/api/growth";
import { DEFAULT_COMPANION_ID } from "@/lib/stores/appStore";

export function useGrowthJournal(companionId?: string | null, enabled = true) {
  const scopedCompanionId = companionId === undefined ? DEFAULT_COMPANION_ID : companionId;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [candidates, setCandidates] = useState<any[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [records, setRecords] = useState<any[]>([]);
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
      const [cr, rr] = await Promise.all([
        listGrowthCandidates(params),
        listGrowthRecords(params),
      ]);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setCandidates((cr as any).items ?? []);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setRecords((rr as any).items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load growth data");
    } finally { setLoading(false); }
  }, [enabled, scopedCompanionId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => { load(); }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  async function act(id: string, fn: () => Promise<unknown>) {
    setActionLock(p => ({ ...p, [id]: true }));
    try { await fn(); await load(); return true; }
    catch (e) { setError(e instanceof Error ? e.message : "Action failed"); return false; }
    finally { setActionLock(p => ({ ...p, [id]: false })); }
  }

  return {
    candidates, records, loading, error, reload: load, actionLock,
    commit: (id: string) => act(id, () => commitGrowth(id)),
    editAndCommit: (id: string, content: string) => act(id, async () => {
      if (!scopedCompanionId) throw new Error("请先选择伙伴");
      await editGrowthCandidate(id, scopedCompanionId, {
        content,
        reason: "用户修改成长理解后确认",
      });
      await commitGrowth(id);
    }),
    reject: (id: string) => act(id, () => rejectGrowth(id, { reason: "Not applicable" })),
    revert: (id: string) => act(id, () => revertGrowthRecord(id, { reason: "Revert understanding update" })),
  };
}
