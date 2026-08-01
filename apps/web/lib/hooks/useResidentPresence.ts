"use client";

import { useCallback, useState } from "react";
import {
  applyMeaningfulSilence,
  createResidentCoPresenceInvitation,
  evaluateResidentPresenceBudget,
  setResidentStatus,
} from "@/lib/api/residentPresence";
import type { CoPresenceInvitationRecord, MeaningfulSilenceResult, PresenceBudgetEvaluation, ResidentStatusRecord } from "@/lib/types";

export function useResidentPresence() {
  const [status, setStatus] = useState<ResidentStatusRecord | null>(null);
  const [budget, setBudget] = useState<PresenceBudgetEvaluation | null>(null);
  const [invitation, setInvitation] = useState<CoPresenceInvitationRecord | null>(null);
  const [silence, setSilence] = useState<MeaningfulSilenceResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async <T,>(task: () => Promise<T>, apply: (value: T) => void) => {
    setSaving(true);
    setError(null);
    try {
      const value = await task();
      apply(value);
      return value;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resident presence request failed");
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  return {
    status,
    budget,
    invitation,
    silence,
    saving,
    error,
    setStatus: (payload: Record<string, unknown>) => run(() => setResidentStatus(payload), setStatus),
    evaluateBudget: (payload: Record<string, unknown>) => run(() => evaluateResidentPresenceBudget(payload), setBudget),
    createInvitation: (payload: Record<string, unknown>) => run(() => createResidentCoPresenceInvitation(payload), setInvitation),
    applySilence: (payload: Record<string, unknown>) => run(() => applyMeaningfulSilence(payload), setSilence),
  };
}
