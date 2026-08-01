"use client";

import { Eraser } from "lucide-react";
import type { RealtimeTraceV5Detail } from "@/lib/types";

export function RedactionPanel({ trace }: { trace: RealtimeTraceV5Detail | null }) {
  const redactions = trace?.redactions ?? [];

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Eraser size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Redaction</h2>
          <p>Raw context is hidden unless explicitly authorized. This UI shows redaction state only.</p>
        </div>
      </div>

      <div className="domain-linked-note">
        Replay and trace screens must not expose unauthorized raw audio, screen, video, or payload references.
      </div>

      <div className="domain-list">
        {redactions.length === 0 ? (
          <div className="domain-inline-empty">No redaction records available.</div>
        ) : redactions.map((redaction, index) => (
          <div key={String(redaction.id ?? index)} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <strong>{String(redaction.redaction_scope ?? redaction.event_type ?? "redaction")}</strong>
              <span className="pill-sm">{String(redaction.redaction_status ?? "pending")}</span>
            </div>
            <pre className="domain-code-block">{JSON.stringify(redaction, null, 2)}</pre>
          </div>
        ))}
      </div>
    </section>
  );
}
