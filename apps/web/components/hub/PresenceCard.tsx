"use client";

import type { PresenceOpportunity } from "@/lib/api/presence";

export function PresenceCard({ presence }: { presence: PresenceOpportunity[] }) {
  return (
    <div className="glass-presence-card" style={{ padding: "22px 20px", minHeight: 260 }}>
      <div style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--echora-text-muted)", marginBottom: 8 }}>
        Quiet Presence
      </div>
      <p style={{ fontSize: "0.82rem", color: "var(--echora-text-secondary)", lineHeight: 1.45, margin: "0 0 10px" }}>
        Echora keeps these here, not in your face.
      </p>
      {(presence || []).length > 0 ? (
        (presence || []).slice(0, 3).map((p: PresenceOpportunity) => (
          <div key={p.id} style={{
            padding: "8px 0", borderBottom: "1px solid rgba(168,255,225,0.2)",
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <div>
              <div style={{ fontSize: "0.85rem", color: "var(--echora-text-primary)" }}>{p.title}</div>
              <div style={{ fontSize: "0.7rem", color: "var(--echora-text-muted)" }}>{p.reason || p.message}</div>
            </div>
            <span style={{ fontSize: "0.7rem", color: "var(--echora-presence-cyan)", fontWeight: 500, padding: "2px 10px", borderRadius: 9999, background: "rgba(168,255,225,0.2)" }}>
              {p.status}
            </span>
          </div>
        ))
      ) : (
        <p style={{ fontSize: "0.82rem", color: "var(--echora-text-secondary)", margin: 0 }}>
          No queued presence right now.
        </p>
      )}
      <a href="/presence" style={{ display: "inline-block", marginTop: 12, color: "var(--echora-accent-blue)", fontSize: "0.82rem", fontWeight: 500, textDecoration: "none" }}>
        View all
      </a>
    </div>
  );
}
