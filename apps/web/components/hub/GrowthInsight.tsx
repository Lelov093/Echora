"use client";

import Link from "next/link";
import { ArrowUpRight, Sparkle } from "lucide-react";

interface GrowthStats {
  pending_growth_candidates?: number;
  growth_records?: number;
}

export function GrowthInsight({ stats }: { stats: GrowthStats }) {
  const pending = stats?.pending_growth_candidates || 0;

  return (
    <section className="dynamic-glass growth-glass" style={{ padding: "1rem", borderRadius: 30 }} aria-label="Growth insight">
      <header style={{ marginBottom: "0.65rem", display: "inline-flex", alignItems: "center", gap: "0.35rem", fontSize: "0.78rem", color: "#b070ad", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600 }}>
        <Sparkle size={14} strokeWidth={1.9} />
        Growth Insight
      </header>

      <p style={{ margin: "0 0 0.75rem", fontSize: "0.9rem", color: "var(--echora-text-secondary)", lineHeight: 1.45 }}>
        Echora&apos;s understanding is being refined based on your preferences and feedback.
      </p>

      <div className="glass-soft" style={{ borderRadius: 20, minHeight: 112, padding: "0.82rem" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
          <div>
            <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--echora-text-muted)" }}>Pending</p>
            <p style={{ margin: "0.15rem 0 0", fontSize: "1.45rem", color: "#a25aa0", fontWeight: 500 }}>{pending}</p>
          </div>

          <div>
            <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--echora-text-muted)" }}>Recent update</p>
            <p style={{ margin: "0.15rem 0 0", fontSize: "0.9rem", color: "var(--echora-text-secondary)", lineHeight: 1.35 }}>
              {pending > 0 ? "Understanding update is waiting for review." : "No committed growth record yet."}
            </p>
          </div>
        </div>
      </div>

      <Link href="/growth" style={{ marginTop: "0.75rem", display: "inline-flex", alignItems: "center", gap: "0.35rem", color: "#9f57a0", textDecoration: "none", fontSize: "0.84rem", fontWeight: 500 }}>
        View Growth Journal
        <ArrowUpRight size={14} strokeWidth={2} />
      </Link>
    </section>
  );
}
