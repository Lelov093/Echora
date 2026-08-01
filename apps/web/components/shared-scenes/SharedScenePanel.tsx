"use client";

import { Compass, Sparkles } from "lucide-react";
import type { SharedSceneBundle } from "@/lib/types";

export function SharedScenePanel({ scene }: { scene: SharedSceneBundle }) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Compass size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>SharedScenePanel</h2>
          <p>共同经历的上下文容器，承接 scene context、experience candidate 和 visibility policy。</p>
        </div>
      </div>

      <div className="domain-stack">
        <div className="domain-chip-row">
          <span className="pill-sm pill-accent">{scene.scene_status}</span>
          <span className="pill-sm">{scene.scene_type}</span>
          <span className="pill-sm">{scene.visibility_scope}</span>
        </div>

        <div className="domain-summary-card glass-soft">
          <div className="domain-summary-title">{scene.scene_title}</div>
          <p>{scene.scene_summary || scene.focal_topic || "No scene summary recorded yet."}</p>
        </div>

        <div className="domain-inline-grid">
          <InfoCard label="Source" value={scene.source_type} />
          <InfoCard label="Events" value={String(scene.events.length)} />
          <InfoCard label="Experiences" value={String(scene.shared_experiences.length)} />
        </div>

        <div className="domain-detail-block">
          <div className="domain-detail-label">Experience status</div>
          <div className="domain-chip-row">
            {scene.shared_experiences.length > 0 ? scene.shared_experiences.map((item) => (
              <span key={item.id} className="pill-sm">
                <Sparkles size={12} strokeWidth={1.8} />
                {item.experience_status}
              </span>
            )) : <span className="domain-inline-empty">No shared experience candidates</span>}
          </div>
        </div>
      </div>
    </section>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-soft domain-info-card">
      <div>
        <div className="domain-info-label">{label}</div>
        <div className="domain-info-value">{value}</div>
      </div>
    </div>
  );
}
