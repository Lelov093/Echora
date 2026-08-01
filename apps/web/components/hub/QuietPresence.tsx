"use client";

import Link from "next/link";
import { ChevronRight, Leaf, CheckSquare, MessageSquare } from "lucide-react";

interface PresenceItem {
  id?: string;
  title?: string;
  reason?: string;
  message?: string;
  status?: string;
}

function PresenceRow({ icon, title, subtitle, status }: { icon: React.ReactNode; title: string; subtitle: string; status: string }) {
  return (
    <div
      className="glass-soft interactive-lift"
      style={{
        minHeight: 80,
        borderRadius: 20,
        padding: "0.8rem",
        display: "grid",
        gridTemplateColumns: "44px 1fr 16px",
        alignItems: "center",
        gap: "0.7rem",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          border: "1px solid rgba(255,255,255,0.86)",
          background: "linear-gradient(135deg, rgba(255,255,255,0.9), rgba(190,243,227,0.56))",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#4cae97",
        }}
      >
        {icon}
      </div>

      <div>
        <p style={{ margin: 0, fontSize: "0.98rem", color: "#2e527e", fontWeight: 500 }}>{title}</p>
        <p style={{ margin: "0.14rem 0 0", fontSize: "0.84rem", color: "var(--echora-text-secondary)" }}>{subtitle}</p>
        <p style={{ margin: "0.18rem 0 0", fontSize: "0.76rem", color: "var(--echora-text-muted)" }}>{status}</p>
      </div>

      <ChevronRight size={15} strokeWidth={1.9} color="#7ba899" />
    </div>
  );
}

export function QuietPresence({ presence }: { presence: PresenceItem[] }) {
  const rows = (presence || []).slice(0, 3);

  return (
    <section className="dynamic-glass presence-glass" style={{ padding: "1rem", borderRadius: 30 }} aria-label="Quiet presence">
      <header style={{ marginBottom: "0.65rem", display: "inline-flex", alignItems: "center", gap: "0.35rem", fontSize: "0.78rem", color: "#4f9e8a", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600 }}>
        <Leaf size={14} strokeWidth={1.9} />
        Quiet Presence
      </header>

      <p style={{ margin: "0 0 0.7rem", fontSize: "0.88rem", color: "var(--echora-text-secondary)" }}>
        Echora keeps these here, not in your face.
      </p>

      <div style={{ display: "grid", gap: "0.5rem" }}>
        {rows.length > 0 ? (
          rows.map((item, index) => (
            <PresenceRow
              key={item.id || index}
              icon={index === 0 ? <MessageSquare size={18} strokeWidth={1.9} /> : <CheckSquare size={18} strokeWidth={1.9} />}
              title={item.title || "Pending presence thread"}
              subtitle={item.reason || item.message || "Waiting for your next interaction."}
              status={item.status || "queued"}
            />
          ))
        ) : (
          <PresenceRow
            icon={<MessageSquare size={18} strokeWidth={1.9} />}
            title="No queued opportunities"
            subtitle="Presence items will appear after meaningful conversation cues."
            status="idle"
          />
        )}
      </div>

      <Link href="/presence" style={{ marginTop: "0.72rem", display: "inline-flex", alignItems: "center", gap: "0.35rem", color: "#3b8f7c", fontSize: "0.84rem", fontWeight: 500, textDecoration: "none" }}>
        View presence queue
        <ChevronRight size={14} strokeWidth={2} />
      </Link>
    </section>
  );
}
