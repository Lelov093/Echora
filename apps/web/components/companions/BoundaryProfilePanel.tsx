"use client";

import { ShieldCheck } from "lucide-react";
import type { CompanionBoundaryProfile } from "@/lib/types";

export function BoundaryProfilePanel({ boundary }: { boundary: CompanionBoundaryProfile | null }) {
  return (
    <section className="dynamic-glass companion-panel">
      <div className="companion-panel-header">
        <div className="companion-panel-icon"><ShieldCheck size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Boundary Profile</h2>
          <p>Memory visibility, review defaults, and presence interruption rules.</p>
        </div>
      </div>

      {boundary ? (
        <div className="companion-panel-body">
          <div className="companion-chip-row">
            <span className="pill-sm">private {boundary.private_memory_default}</span>
            <span className="pill-sm">shared {boundary.shared_memory_default}</span>
            <span className="pill-sm">global {boundary.global_memory_read_scope}</span>
          </div>
          <Block label="Cross-Companion Read Policy" value={boundary.cross_companion_read_policy} />
          <Block label="Presence Interrupt Policy" value={boundary.presence_interrupt_policy} />
          <div className="companion-check-row">
            <CheckItem label="Private to shared review" value={boundary.review_required_private_to_shared} />
            <CheckItem label="Shared to private review" value={boundary.review_required_shared_to_private} />
            <CheckItem label="Cross-companion review" value={boundary.review_required_cross_companion_share} />
          </div>
        </div>
      ) : (
        <div className="companion-panel-empty">Boundary profile is not available.</div>
      )}
    </section>
  );
}

function Block({ label, value }: { label: string; value: string }) {
  return (
    <div className="companion-detail-block">
      <div className="companion-detail-label">{label}</div>
      <div className="companion-detail-value">{value}</div>
    </div>
  );
}

function CheckItem({ label, value }: { label: string; value: boolean }) {
  return (
    <div className="companion-check-item">
      <span>{label}</span>
      <span className={`pill-sm ${value ? "pill-accent" : ""}`}>{value ? "required" : "off"}</span>
    </div>
  );
}
