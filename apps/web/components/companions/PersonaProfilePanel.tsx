"use client";

import { MessageCircleMore } from "lucide-react";
import type { CompanionPersonaProfile } from "@/lib/types";

export function PersonaProfilePanel({ profile }: { profile: CompanionPersonaProfile | null }) {
  return (
    <section className="dynamic-glass companion-panel">
      <div className="companion-panel-header">
        <div className="companion-panel-icon"><MessageCircleMore size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Persona Profile</h2>
          <p>Stable style, tone, and drift guard settings for long-term consistency.</p>
        </div>
      </div>

      {profile ? (
        <div className="companion-panel-body">
          <Block label="Persona Summary" value={profile.persona_summary || "No persona summary recorded yet."} />
          <Block label="Communication Style" value={profile.communication_style_summary || "No communication style summary recorded yet."} />
          <div className="companion-chip-row">
            <span className="pill-sm">lock {profile.persona_lock_level}</span>
            <span className="pill-sm">drift {profile.drift_guard_level}</span>
            <span className="pill-sm">presence {profile.presence_style}</span>
          </div>
          <TagRow label="Tone Descriptors" items={profile.tone_descriptors_json} />
          <TagRow label="Core Values" items={profile.core_values_json} />
        </div>
      ) : (
        <div className="companion-panel-empty">Persona profile is not available.</div>
      )}
    </section>
  );
}

function Block({ label, value }: { label: string; value: string }) {
  return (
    <div className="companion-detail-block">
      <div className="companion-detail-label">{label}</div>
      <div className="companion-detail-value">{value}</div>
    </div>
  );
}

function TagRow({ label, items }: { label: string; items: unknown[] }) {
  const values = items.map((item) => String(item)).filter(Boolean);
  return (
    <div className="companion-detail-block">
      <div className="companion-detail-label">{label}</div>
      <div className="companion-chip-row">
        {values.length > 0 ? values.map((item) => <span key={item} className="pill-sm">{item}</span>) : <span className="companion-inline-empty">No items recorded</span>}
      </div>
    </div>
  );
}
