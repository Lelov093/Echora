"use client";

import Link from "next/link";
import { ChevronRight, MessageCircle, Layers, Sparkles, Leaf, ShieldCheck } from "lucide-react";

const SHORTCUTS = [
  { href: "/conversation", label: "Conversation", icon: MessageCircle },
  { href: "/memory", label: "Memory Center", icon: Layers },
  { href: "/growth", label: "Growth Journal", icon: Sparkles },
  { href: "/presence", label: "Presence Queue", icon: Leaf },
  { href: "/settings", label: "Boundary Studio", icon: ShieldCheck },
] as const;

export function HubShortcutBar() {
  return (
    <section className="shortcut-wrap dynamic-glass" aria-label="Hub shortcuts">
      <div className="shortcut-grid">
        {SHORTCUTS.map((item) => {
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} className="shortcut-item glass-soft interactive-lift" style={{ borderRadius: 22 }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.62rem" }}>
                <span
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: "50%",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "linear-gradient(135deg, rgba(255,255,255,0.92), rgba(202,220,249,0.62))",
                    border: "1px solid rgba(255,255,255,0.88)",
                    color: "#4a78b8",
                  }}
                >
                  <Icon size={18} strokeWidth={1.9} />
                </span>

                <span style={{ fontSize: "1rem", color: "#2f517e", fontWeight: 500 }}>{item.label}</span>
              </span>

              <ChevronRight size={16} strokeWidth={2} color="#6f89ac" />
            </Link>
          );
        })}
      </div>
    </section>
  );
}
