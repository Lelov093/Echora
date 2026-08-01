"use client";

import { Activity, Focus, ShieldCheck, ChevronRight } from "lucide-react";

interface ContinuityData {
  conversation_id?: string;
  current_topic?: string;
  current_goal?: string;
  open_threads?: string[];
  last_message_at?: string;
}

function formatTime(value?: string) {
  if (!value) return "No activity yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "No activity yet";
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function StackCard({ icon, title, body, foot }: { icon: React.ReactNode; title: string; body: string; foot: string }) {
  return (
    <article className="glass-soft interactive-lift" style={{ minHeight: 156, padding: "1.05rem", display: "grid", gridTemplateColumns: "48px 1fr 18px", alignItems: "start", gap: "0.8rem" }}>
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, rgba(255,255,255,0.9), rgba(189,214,245,0.55))",
          border: "1px solid rgba(255,255,255,0.86)",
          boxShadow: "0 8px 20px rgba(120,160,210,0.16)",
        }}
      >
        {icon}
      </div>

      <div>
        <h3 style={{ margin: "0.12rem 0 0.2rem", fontSize: "1.04rem", fontWeight: 500, color: "#244575" }}>{title}</h3>
        <p style={{ margin: 0, color: "var(--echora-text-secondary)", fontSize: "0.92rem", lineHeight: 1.45 }}>{body}</p>
        <p style={{ margin: "0.45rem 0 0", color: "var(--echora-text-muted)", fontSize: "0.77rem" }}>{foot}</p>
      </div>

      <div style={{ marginTop: "0.22rem", color: "var(--echora-text-muted)" }}>
        <ChevronRight size={15} strokeWidth={1.8} />
      </div>
    </article>
  );
}

export function ContinuityStack({ continuity }: { continuity: ContinuityData }) {
  const ongoingBody = continuity?.current_topic || "No active thread yet.";
  const focusBody = continuity?.current_goal || "No current focus recorded.";

  const boundaryBody = "Memory commit requires review.";

  return (
    <section className="dynamic-glass memory-glass" style={{ padding: "1rem", borderRadius: 30 }} aria-label="Continuity stack">
      <header style={{ marginBottom: "0.7rem", paddingLeft: "0.2rem", fontSize: "0.78rem", color: "#6781a4", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 500 }}>
        Continuity Stack
      </header>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem" }}>
        <StackCard
          icon={<Activity size={19} strokeWidth={1.8} color="#4a84d8" />}
          title="Ongoing Thread"
          body={ongoingBody}
          foot={`Last active  •  ${formatTime(continuity?.last_message_at)}`}
        />

        <StackCard
          icon={<Focus size={19} strokeWidth={1.8} color="#4a84d8" />}
          title="Current Focus"
          body={focusBody}
          foot={continuity?.conversation_id ? "Thread is active" : "Waiting for next run"}
        />

        <StackCard
          icon={<ShieldCheck size={19} strokeWidth={1.8} color="#4a84d8" />}
          title="Boundary Summary"
          body={boundaryBody}
          foot="Status  •  Review needed"
        />
      </div>
    </section>
  );
}
