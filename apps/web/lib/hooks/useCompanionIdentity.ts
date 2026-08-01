"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getCompanionBoundary,
  getCompanionContract,
  getCompanionIdentity,
  getCompanionPersona,
  patchCompanionBoundary,
  patchCompanionContract,
  patchCompanionIdentity,
  patchCompanionPersona,
} from "@/lib/api/companionIdentity";
import type {
  CompanionBoundaryProfile,
  CompanionIdentityProfile,
  CompanionPersonaProfile,
  CompanionRelationshipContract,
} from "@/lib/types";

interface CompanionIdentityState {
  identity: CompanionIdentityProfile | null;
  persona: CompanionPersonaProfile | null;
  contract: CompanionRelationshipContract | null;
  boundary: CompanionBoundaryProfile | null;
}

export function useCompanionIdentity(companionId: string | null) {
  const [data, setData] = useState<CompanionIdentityState>({
    identity: null,
    persona: null,
    contract: null,
    boundary: null,
  });
  const [loading, setLoading] = useState(Boolean(companionId));
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!companionId) {
      setData({ identity: null, persona: null, contract: null, boundary: null });
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [identity, persona, contract, boundary] = await Promise.all([
        getCompanionIdentity(companionId),
        getCompanionPersona(companionId),
        getCompanionContract(companionId),
        getCompanionBoundary(companionId),
      ]);
      setData({ identity, persona, contract, boundary });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load companion identity");
    } finally {
      setLoading(false);
    }
  }, [companionId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    load();
  }, [load]);
  /* eslint-enable react-hooks/set-state-in-effect */

  return {
    ...data,
    loading,
    error,
    reload: load,
    patchIdentity: async (payload: Record<string, unknown>) => {
      if (!companionId) return null;
      const identity = await patchCompanionIdentity(companionId, payload);
      setData((current) => ({ ...current, identity }));
      return identity;
    },
    patchPersona: async (payload: Record<string, unknown>) => {
      if (!companionId) return null;
      const persona = await patchCompanionPersona(companionId, payload);
      setData((current) => ({ ...current, persona }));
      return persona;
    },
    patchContract: async (payload: Record<string, unknown>) => {
      if (!companionId) return null;
      const contract = await patchCompanionContract(companionId, payload);
      setData((current) => ({ ...current, contract }));
      return contract;
    },
    patchBoundary: async (payload: Record<string, unknown>) => {
      if (!companionId) return null;
      const boundary = await patchCompanionBoundary(companionId, payload);
      setData((current) => ({ ...current, boundary }));
      return boundary;
    },
  };
}
