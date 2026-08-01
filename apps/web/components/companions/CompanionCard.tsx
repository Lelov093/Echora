"use client";

import Link from "next/link";
import { ArrowRight, Shield, Sparkles, UserRound } from "lucide-react";
import type { CompanionBundle } from "@/lib/types";

export function CompanionCard({ companion }: { companion: CompanionBundle }) {
  return (
    <Link
      href={`/companions/${companion.id}`}
      className="glass-soft companion-card"
      style={{ textDecoration: "none", display: "grid", gap: "0.95rem", padding: "1.1rem" }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.8rem", alignItems: "flex-start" }}>
        <div style={{ display: "grid", gap: "0.22rem", minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem", flexWrap: "wrap" }}>
            <span className="companion-card-title">{companion.name}</span>
            <span className="pill-sm">{companion.current_status}</span>
          </div>
          <p className="companion-card-subtitle">
            {companion.subtitle || companion.identity_profile_status || "Long-lived cyber companion"}
          </p>
        </div>
        <div className="companion-card-arrow">
          <ArrowRight size={16} strokeWidth={1.8} />
        </div>
      </div>

      <p className="companion-card-summary">
        {companion.base_personality || companion.identity_prompt || "Identity and relationship contract available for inspection."}
      </p>

      <div className="companion-card-meta">
        <div className="companion-card-chip">
          <Sparkles size={14} strokeWidth={1.8} />
          <span>{companion.current_mode}</span>
        </div>
        <div className="companion-card-chip">
          <UserRound size={14} strokeWidth={1.8} />
          <span>{companion.relationship_role || "companion"}</span>
        </div>
        <div className="companion-card-chip">
          <Shield size={14} strokeWidth={1.8} />
          <span>{companion.boundary_scope || "scoped boundary"}</span>
        </div>
      </div>
    </Link>
  );
}
