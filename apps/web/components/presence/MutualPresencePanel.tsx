"use client";

import type { PresenceOpportunity } from "@/lib/api/presence";

export function MutualPresencePanel({ items }: { items: PresenceOpportunity[] }) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon">M</div>
        <div>
          <h2>MutualPresencePanel</h2>
          <p>展示 quiet-first 的 presence 机会，以及 meaningful silence 何时优先于打扰。</p>
        </div>
      </div>

      <div className="domain-list">
        {items.length > 0 ? items.map((item) => (
          <div key={item.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{item.title || item.type || "Presence opportunity"}</strong>
                <div className="domain-list-sub">{item.status} · {item.recommended_surface || "hub_queue"}</div>
              </div>
            </div>
            <p className="domain-card-copy">{item.reason || item.summary || "No presence note recorded."}</p>
            {item.meaningful_silence_reason && <div className="domain-linked-note">{item.meaningful_silence_reason}</div>}
          </div>
        )) : <div className="domain-inline-empty">No presence opportunities.</div>}
      </div>
    </section>
  );
}
