"use client";

import { useCallback, useEffect, useState } from "react";
import * as memApi from "@/lib/api/memories";
import type { MemoryItem, MemoryCandidate } from "@/lib/api/memories";
import { DEFAULT_COMPANION_ID } from "@/lib/stores/appStore";

export function useMemoryControlCenter(companionId?: string | null, enabled = true) {
  const scopedCompanionId = companionId === undefined ? DEFAULT_COMPANION_ID : companionId;
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [candidates, setCandidates] = useState<MemoryCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      const [mr, cr] = await Promise.all([
        memApi.listMemories(params),
        memApi.listMemoryCandidates(params),
      ]);
      setMemories((mr as { data?: { items?: MemoryItem[] }; items?: MemoryItem[] }).data?.items || (mr as { items?: MemoryItem[] }).items || []);
      setCandidates((cr as { data?: { items?: MemoryCandidate[] }; items?: MemoryCandidate[] }).data?.items || (cr as { items?: MemoryCandidate[] }).items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load memory data");
    } finally { setLoading(false); }
  }, [enabled, scopedCompanionId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => { load(); }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  async function memAction(fn: () => Promise<unknown>) { await fn(); await load(); }

  async function candidateAction(fn: () => Promise<unknown>) { await fn(); await load(); }

  const activeMems = memories.filter(m => m.state === "active");
  const dormantMems = memories.filter(m => m.state === "dormant");
  const archivedMems = memories.filter(m => m.state === "archived");
  const pendingCands = candidates.filter(c => c.status === "pending");
  const acceptedCands = candidates.filter(c => c.status === "accepted");

  return {
    memories, candidates, loading, error, reload: load,
    activeMems, dormantMems, archivedMems, pendingCands, acceptedCands,
    memAction, candidateAction,
    lockMemory: (id: string) => memApi.lockMemory(id, scopedCompanionId!),
    fadeMemory: (id: string, data?: Record<string, unknown>) => memApi.fadeMemory(id, scopedCompanionId!, data),
    archiveMemory: (id: string) => memApi.archiveMemory(id, scopedCompanionId!),
    reactivateMemory: (id: string) => memApi.reactivateMemory(id, scopedCompanionId!),
    deleteMemory: (id: string) => memApi.deleteMemory(id, scopedCompanionId!),
    acceptCandidate: memApi.acceptCandidate, commitCandidate: memApi.commitCandidate,
    rejectCandidate: memApi.rejectCandidate,
  };
}
