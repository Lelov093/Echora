"use client";

import { ArrowRight, Layers3 } from "lucide-react";

interface MemoryItem {
  id?: string;
  summary?: string;
  content?: string;
  type?: string;
  state?: string;
  memory_strength?: number;
  updated_at?: string;
  created_at?: string;
}

interface StreamRow {
  key: string;
  text: string;
  type?: string;
  state?: string;
  strength?: number;
  time?: string;
  empty: boolean;
}

function dedupMemories(list: MemoryItem[]) {
  const seen = new Set<string>();
  return list.filter((item) => {
    const key = (item.summary || item.content || "").trim().slice(0, 90);
    if (!key) return false;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function timeLabel(raw?: string) {
  if (!raw) return "--";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "--";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MemoryRow({ text, type, state, strength, time, empty }: { text: string; type?: string; state?: string; strength?: number; time?: string; empty?: boolean }) {
  return (
    <div
      className="interactive-lift"
      style={{
        minHeight: 40,
        display: "grid",
        gridTemplateColumns: "18px 1fr auto",
        gap: "0.7rem",
        alignItems: "center",
        borderRadius: 16,
        border: "1px solid rgba(255,255,255,0.82)",
        background: "linear-gradient(135deg, rgba(255,255,255,0.82), rgba(184,203,241,0.24))",
        padding: "0.42rem 0.72rem",
      }}
    >
      <div style={{ display: "flex", justifyContent: "center" }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            border: "2px solid rgba(122,165,228,0.56)",
            background: empty ? "rgba(255,255,255,0.78)" : "rgba(112,162,236,0.86)",
            boxShadow: empty ? "none" : "0 0 10px rgba(112,162,236,0.4)",
          }}
        />
      </div>

      <div>
        <p style={{ margin: 0, fontSize: "0.95rem", color: empty ? "var(--echora-text-secondary)" : "#244b80", lineHeight: 1.35 }}>{text}</p>
        {!empty ? (
          <p style={{ margin: "0.12rem 0 0", fontSize: "0.76rem", color: "var(--echora-text-muted)" }}>
            {type || "memory"}  •  {state || "active"}  •  strength {typeof strength === "number" ? strength.toFixed(2) : "--"}
          </p>
        ) : null}
      </div>

      <span style={{ color: "var(--echora-text-muted)", fontSize: "0.75rem" }}>{time || ""}</span>
    </div>
  );
}

export function MemoryStream({ memories }: { memories: MemoryItem[] }) {
  const real = dedupMemories(memories || []).slice(0, 5);

  const emptySlots = [
    "More committed memories will appear here.",
    "Commit a memory candidate to start the stream.",
    "Accepted memories will shape future responses.",
  ];

  const rows: StreamRow[] =
    real.length > 0
      ? real.map((item) => ({
          key: item.id || `${item.summary || item.content}`,
          text: item.summary || (item.content || "").slice(0, 120),
          type: item.type,
          state: item.state,
          strength: item.memory_strength,
          time: timeLabel(item.updated_at || item.created_at),
          empty: false,
        }))
      : emptySlots.map((slot, idx) => ({
          key: `empty-${idx}`,
          text: slot,
          empty: true,
        }));

  return (
    <section className="dynamic-glass memory-glass" style={{ padding: "1.1rem", borderRadius: 30 }} aria-label="Memory stream">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.7rem" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", fontSize: "0.78rem", color: "#6781a4", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 500 }}>
          <Layers3 size={14} strokeWidth={1.9} />
          Memory Stream
        </div>

        <span className="glass-pill" style={{ height: 28, fontSize: "0.72rem", padding: "0 0.65rem" }}>
          Live
        </span>
      </header>

      <div style={{ display: "grid", gap: "0.42rem", position: "relative", paddingLeft: "0.25rem" }}>
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            left: 13,
            top: 8,
            bottom: 8,
            width: 2,
            borderRadius: 99,
            background: "linear-gradient(180deg, rgba(124,168,230,0.44), rgba(124,168,230,0.08))",
          }}
        />

        {rows.map((row) => (
          <MemoryRow
            key={row.key}
            text={row.text}
            type={row.type}
            state={row.state}
            strength={row.strength}
            time={row.time}
            empty={row.empty}
          />
        ))}
      </div>

      <div style={{ marginTop: "0.75rem", display: "inline-flex", alignItems: "center", gap: "0.35rem", color: "#366eb8", fontSize: "0.86rem", fontWeight: 500 }}>
        <span>Open memory center</span>
        <ArrowRight size={14} strokeWidth={2} />
      </div>
    </section>
  );
}
