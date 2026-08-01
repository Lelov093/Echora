"use client";

import { AlertCircle, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CompanionCreatePanel } from "@/components/companions/CompanionCreatePanel";
import { SectionNav } from "@/components/navigation/SectionNav";
import { useUIStore } from "@/lib/stores/appStore";
import { useCompanionRoster } from "@/lib/hooks/useCompanionRoster";
import { CompanionRoster } from "@/components/companions/CompanionRoster";
import { companionNavItems } from "@/lib/navigation/routes";

export default function CompanionsPageBody() {
  const router = useRouter();
  const { items, loading, error, reload, create: createCompanion } = useCompanionRoster();
  const setActiveCompanionId = useUIStore((state) => state.setActiveCompanionId);
  const [creating, setCreating] = useState(false);
  const [createMessage, setCreateMessage] = useState<string | null>(null);

  const handleCreate = async (payload: Record<string, unknown>) => {
    setCreating(true);
    setCreateMessage("Creating companion...");
    try {
      const companion = await createCompanion(payload);
      await reload();
      setActiveCompanionId(companion.id);
      setCreateMessage("Companion created");
      router.push(companion.first_meeting_conversation_id ? `/companions/${companion.id}/conversations/${companion.first_meeting_conversation_id}` : `/companions/${companion.id}`);
    } catch (e) {
      setCreateMessage(e instanceof Error ? e.message : "Create failed");
      throw e;
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
    <SectionNav title="Companions" eyebrow="Identity, co-presence, shared scenes" items={companionNavItems} />
    <main className="echora-page companions-page">
      <section className="dynamic-glass companion-page-hero">
        <div>
          <div className="companion-chip-row">
            <span className="pill-sm pill-accent">多伙伴</span>
            <span className="pill-sm">{items.length} companion{items.length === 1 ? "" : "s"}</span>
          </div>
          <h1>Companion Roster</h1>
          <p>
            Each companion is treated as a long-term cyber companion individual with identity, persona,
            relationship contract, memory scope, and boundary rules.
          </p>
        </div>
        <div className="companion-hero-badge">
          <Users size={22} strokeWidth={1.8} />
        </div>
      </section>

      <CompanionCreatePanel creating={creating} message={createMessage} onCreate={handleCreate} />

      {loading ? (
        <section className="glass-soft companion-feedback-panel">
          <p>Loading companion roster...</p>
        </section>
      ) : error ? (
        <section className="glass-soft companion-feedback-panel">
          <AlertCircle size={18} strokeWidth={1.8} style={{ color: "#bd5b76" }} />
          <div>
            <p>Companion roster could not be loaded.</p>
            <button type="button" className="glass-btn glass-btn-secondary" onClick={reload}>Retry</button>
          </div>
        </section>
      ) : (
        <CompanionRoster companions={items} />
      )}
    </main>
    </>
  );
}
