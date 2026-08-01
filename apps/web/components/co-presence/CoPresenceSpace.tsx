"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Blocks, Eye, Users } from "lucide-react";
import type { CoPresenceSessionBundle, CompanionBundle } from "@/lib/types";

export function CoPresenceSpace({
  session,
  companions,
}: {
  session: CoPresenceSessionBundle;
  companions: CompanionBundle[];
}) {
  const resolveCompanion = (companionId: string | null | undefined) =>
    companions.find((item) => item.id === companionId)?.name || "Unknown companion";

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Users size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>CoPresenceSpace</h2>
          <p>共同在场不是普通群聊。这里展示谁在场、谁参与、谁旁听，以及谁能形成记忆。</p>
        </div>
      </div>

      <div className="domain-stack">
        <div className="domain-chip-row">
          <span className="pill-sm pill-accent">{session.session_status}</span>
          <span className="pill-sm">{session.visibility_scope}</span>
          <span className="pill-sm">{session.session_source}</span>
        </div>

        <div className="domain-summary-card glass-soft">
          <div className="domain-summary-title">{session.session_title}</div>
          <p>{session.session_summary || session.entry_reason || "No session summary recorded yet."}</p>
        </div>

        <div className="domain-inline-grid">
          <InfoCard icon={<Blocks size={14} strokeWidth={1.8} />} label="Primary companion" value={resolveCompanion(session.primary_companion_id)} />
          <InfoCard icon={<Users size={14} strokeWidth={1.8} />} label="Participants" value={String(session.participants.length)} />
          <InfoCard icon={<Eye size={14} strokeWidth={1.8} />} label="Observing policy" value={session.policy?.default_observing_memory_participation || "none"} />
        </div>

        <div className="domain-detail-block">
          <div className="domain-detail-label">Shared scenes in this session</div>
          <div className="domain-chip-row">
            {session.shared_scene_ids.length > 0 ? session.shared_scene_ids.map((sceneId) => (
              <Link key={sceneId} href={`/scenes?scene=${sceneId}`} className="domain-link-chip">
                {sceneId.slice(0, 8)}
              </Link>
            )) : <span className="domain-inline-empty">No shared scenes yet.</span>}
          </div>
        </div>
      </div>
    </section>
  );
}

function InfoCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="glass-soft domain-info-card">
      <div className="domain-info-icon">{icon}</div>
      <div>
        <div className="domain-info-label">{label}</div>
        <div className="domain-info-value">{value}</div>
      </div>
    </div>
  );
}
