"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, ChevronLeft } from "lucide-react";
import { CompanionDetail } from "@/components/companions/CompanionDetail";
import { getCompanion, updateCompanion } from "@/lib/api/companions";
import { useCompanionIdentity } from "@/lib/hooks/useCompanionIdentity";
import type { CompanionBundle } from "@/lib/types";

export default function CompanionDetailPageBody() {
  const params = useParams<{ companion_id: string }>();
  const companionId = typeof params?.companion_id === "string" ? params.companion_id : null;
  const [companion, setCompanion] = useState<CompanionBundle | null>(null);
  const [loading, setLoading] = useState(Boolean(companionId));
  const [error, setError] = useState<string | null>(null);
  const identityState = useCompanionIdentity(companionId);

  const loadCompanion = useCallback(async () => {
    if (!companionId) {
      setCompanion(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getCompanion(companionId);
      setCompanion(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load companion");
    } finally {
      setLoading(false);
    }
  }, [companionId]);

  useEffect(() => {
    let active = true;
    async function run() {
      if (!companionId) {
        if (active) {
          setCompanion(null);
          setLoading(false);
        }
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const data = await getCompanion(companionId);
        if (active) setCompanion(data);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load companion");
      } finally {
        if (active) setLoading(false);
      }
    }
    run();
    return () => {
      active = false;
    };
  }, [companionId]);

  const saveCompanion = async (payload: Record<string, unknown>) => {
    if (!companionId) return null;
    const updated = await updateCompanion(companionId, payload);
    setCompanion(updated);
    await identityState.reload();
    return updated;
  };

  const combinedLoading = loading || identityState.loading;
  const combinedError = error || identityState.error;

  return (
    <main className="echora-page companions-page">
      <div style={{ marginTop: "1rem", marginBottom: "1rem" }}>
        <Link href="/companions" className="companion-back-link">
          <ChevronLeft size={16} strokeWidth={1.8} />
          <span>Back to roster</span>
        </Link>
      </div>

      {combinedLoading ? (
        <section className="glass-soft companion-feedback-panel">
          <p>Loading companion detail...</p>
        </section>
      ) : combinedError || !companion ? (
        <section className="glass-soft companion-feedback-panel">
          <AlertCircle size={18} strokeWidth={1.8} style={{ color: "#bd5b76" }} />
          <div>
            <p>Companion detail could not be loaded.</p>
            <p style={{ margin: 0, color: "var(--echora-text-secondary)", fontSize: "0.84rem" }}>
              {combinedError || "Companion not found."}
            </p>
          </div>
        </section>
      ) : (
        <CompanionDetail
          companion={companion}
          identity={identityState.identity}
          persona={identityState.persona}
          contract={identityState.contract}
          boundary={identityState.boundary}
          onReload={loadCompanion}
          onSaveCompanion={saveCompanion}
          onSaveIdentity={identityState.patchIdentity}
          onSavePersona={identityState.patchPersona}
          onSaveContract={identityState.patchContract}
          onSaveBoundary={identityState.patchBoundary}
        />
      )}
    </main>
  );
}
