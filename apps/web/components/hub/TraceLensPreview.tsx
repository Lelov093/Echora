"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface TraceLensPreviewProps {
  hasTrace: boolean;
}

const NODE_CONFIG = [
  { key: "memory", label: "Memory", color: "#63a9f2" },
  { key: "growth", label: "Growth", color: "#9b7cf0" },
  { key: "presence", label: "Presence", color: "#68e0cf" },
] as const;

export function TraceLensPreview({ hasTrace }: TraceLensPreviewProps) {
  return (
    <section className="dynamic-glass trace-glass" style={{ padding: "1rem", borderRadius: 30 }} aria-label="Trace lens preview">
      <header style={{ marginBottom: "0.65rem", fontSize: "0.78rem", color: "#6c7fb4", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 500 }}>
        Trace Lens Preview
      </header>

      <div
        style={{
          borderRadius: 20,
          border: "1px solid rgba(255,255,255,0.84)",
          background: "linear-gradient(145deg, rgba(255,255,255,0.8), rgba(208,217,247,0.28))",
          padding: "0.9rem",
        }}
      >
        <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--echora-text-secondary)" }}>
          {hasTrace ? "Last run path" : "Run a conversation to generate a trace."}
        </p>

        <p style={{ margin: "0.26rem 0 0", fontSize: "1.05rem", color: "#2e507e", fontWeight: 500 }}>
          memory → growth → presence
        </p>

        <div style={{ marginTop: "0.9rem", position: "relative", padding: "0.45rem 0.4rem 0.1rem" }}>
          <div
            aria-hidden="true"
            style={{
              position: "absolute",
              left: "12%",
              right: "12%",
              top: 21,
              height: 2,
              borderRadius: 10,
              background: "linear-gradient(90deg, rgba(99,169,242,0.46), rgba(155,124,240,0.46), rgba(104,224,207,0.46))",
            }}
          />

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: "0.6rem" }}>
            {NODE_CONFIG.map((node) => (
              <div key={node.key} style={{ textAlign: "center" }}>
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    margin: "0 auto",
                    border: "2px solid rgba(255,255,255,0.86)",
                    background: `radial-gradient(circle at 35% 35%, rgba(255,255,255,0.95), ${node.color})`,
                    boxShadow: `0 0 18px ${node.color}66`,
                  }}
                />
                <p style={{ margin: "0.36rem 0 0", fontSize: "0.82rem", color: "#325380", fontWeight: 500 }}>{node.label}</p>
              </div>
            ))}
          </div>
        </div>

        <Link href="/conversation" style={{ marginTop: "0.75rem", display: "inline-flex", alignItems: "center", gap: "0.35rem", textDecoration: "none", color: "#336db8", fontSize: "0.84rem", fontWeight: 500 }}>
          Open reasoning path
          <ArrowRight size={14} strokeWidth={2} />
        </Link>
      </div>
    </section>
  );
}
