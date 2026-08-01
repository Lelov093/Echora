"use client";

export function GrowthCard({ stats }: { stats: Record<string, unknown> }) {
  return (
    <div className="glass-growth-card" style={{ padding: "22px 20px", minHeight: 210 }}>
      <div style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--echora-text-muted)", marginBottom: 8 }}>
        Growth Insight
      </div>
      <p style={{ fontSize: "0.85rem", color: "var(--echora-text-secondary)", lineHeight: 1.5, margin: "0 0 8px" }}>
        Understanding is refined from your corrections. All changes are reviewable and reversible.
      </p>
      <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.4rem", fontWeight: 500, color: "var(--echora-text-primary)" }}>
            {String(stats?.pending_growth_candidates ?? 0)}
          </div>
          <div style={{ fontSize: "0.68rem", color: "var(--echora-text-muted)" }}>Pending</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.4rem", fontWeight: 500, color: "var(--echora-text-primary)" }}>
            --
          </div>
          <div style={{ fontSize: "0.68rem", color: "var(--echora-text-muted)" }}>Recent update</div>
        </div>
      </div>
      <a href="/growth" style={{ display: "inline-block", marginTop: 14, color: "var(--echora-accent-blue)", fontSize: "0.82rem", fontWeight: 500, textDecoration: "none" }}>
        View Growth Journal
      </a>
    </div>
  );
}
