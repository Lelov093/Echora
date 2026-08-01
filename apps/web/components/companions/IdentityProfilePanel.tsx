"use client";

import { BadgeInfo } from "lucide-react";
import type { CompanionIdentityProfile } from "@/lib/types";

export function IdentityProfilePanel({ profile }: { profile: CompanionIdentityProfile | null }) {
  return (
    <section className="dynamic-glass companion-panel">
      <div className="companion-panel-header">
        <div className="companion-panel-icon"><BadgeInfo size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Identity Profile</h2>
          <p>Who this companion is across time, not just how it talks in one prompt.</p>
        </div>
      </div>

      {profile ? (
        <div className="companion-panel-body">
          <Block label="Display Name" value={profile.display_name} />
          <Block label="Identity Summary" value={profile.identity_summary} />
          <Block label="Self-Continuity" value={profile.self_continuity_summary || "No continuity summary recorded yet."} />
          <Block label="Origin Story" value={profile.origin_story || "No origin story recorded yet."} />
          <TagRow label="Traits" items={profile.core_traits_json} />
          <TagRow label="Labels" items={profile.identity_labels_json} />
        </div>
      ) : (
        <div className="companion-panel-empty">Identity profile is not available.</div>
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
