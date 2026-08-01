"use client";

import { Users } from "lucide-react";
import type { CompanionBundle } from "@/lib/types";
import { CompanionCard } from "./CompanionCard";

export function CompanionRoster({ companions }: { companions: CompanionBundle[] }) {
  return (
    <section className="companion-roster-grid">
      {companions.map((companion) => (
        <CompanionCard key={companion.id} companion={companion} />
      ))}
      {companions.length === 0 && (
        <div className="glass-soft companion-empty-card">
          <Users size={20} strokeWidth={1.8} style={{ color: "var(--echora-text-muted)" }} />
          <p style={{ margin: 0, fontSize: "0.95rem", color: "var(--echora-text-primary)" }}>No companions available yet.</p>
          <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--echora-text-secondary)" }}>
            每位伙伴都拥有独立的身份、关系、记忆与成长空间。
          </p>
        </div>
      )}
    </section>
  );
}
