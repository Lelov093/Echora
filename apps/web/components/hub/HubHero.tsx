"use client";

import Link from "next/link";
import { Layers, Orbit, Sparkles, CircleDashed } from "lucide-react";
import { CompanionOrb } from "@/components/hub/CompanionOrb";

interface HubHeroProps {
  modeLabel: string;
  activeMemories: number;
  pendingReviews: number;
  queuedPresence: number;
}

function HeroPill({ icon, text, tint }: { icon: React.ReactNode; text: string; tint: "blue" | "lavender" | "mint" | "pink" }) {
  const bg = {
    blue: "rgba(172, 224, 249, 0.26)",
    lavender: "rgba(185, 182, 229, 0.24)",
    mint: "rgba(168, 255, 225, 0.24)",
    pink: "rgba(240, 207, 253, 0.24)",
  }[tint];

  return (
    <span className="glass-pill" style={{ background: `linear-gradient(135deg, rgba(255,255,255,0.82), ${bg})` }}>
      {icon}
      <span>{text}</span>
    </span>
  );
}

export function HubHero({ modeLabel, activeMemories, pendingReviews, queuedPresence }: HubHeroProps) {
  return (
    <section className="hero-field dynamic-glass" aria-label="Companion hero" data-echora-hero-frame>
      <div style={{ position: "relative", zIndex: 2, display: "flex", height: "100%", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" }}>
        <CompanionOrb />

        <h1
          style={{
            margin: "1rem 0 0.3rem",
            fontSize: "3.45rem",
            lineHeight: 1.06,
            fontWeight: 500,
            color: "#1f3f73",
            letterSpacing: "0.005em",
            fontFamily: '"Iowan Old Style", "Palatino Linotype", serif',
          }}
        >
          Welcome back
        </h1>

        <p style={{ margin: 0, color: "#3d5882", fontSize: "1.08rem" }}>
          Echora remembers the thread we were shaping.
        </p>

        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0.65rem", marginTop: "1rem" }}>
          <HeroPill icon={<Orbit size={14} strokeWidth={1.8} color="#3f7fd3" />} text={`${modeLabel} mode`} tint="blue" />
          <HeroPill icon={<Layers size={14} strokeWidth={1.8} color="#5a8ecf" />} text={`${activeMemories} memories`} tint="lavender" />
          <HeroPill icon={<CircleDashed size={14} strokeWidth={1.8} color="#7b7ec5" />} text={`${pendingReviews} reviews`} tint="pink" />
          <HeroPill icon={<Sparkles size={14} strokeWidth={1.8} color="#48a792" />} text={`${queuedPresence} presence`} tint="mint" />
        </div>

        <div style={{ display: "flex", gap: "0.7rem", marginTop: "0.95rem", flexWrap: "wrap", justifyContent: "center" }}>
          <Link href="/conversation" className="glass-btn glass-btn-primary" aria-label="Continue conversation">
            Continue Conversation
          </Link>
          <Link href="/conversation" className="glass-btn glass-btn-secondary" aria-label="Open trace lens">
            Trace Lens
          </Link>
        </div>
      </div>
    </section>
  );
}
