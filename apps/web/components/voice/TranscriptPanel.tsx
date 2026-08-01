"use client";

import { Captions } from "lucide-react";
import type { CompanionVoiceSessionBundle, JsonObject } from "@/lib/types";

function preview(item: JsonObject) {
  return String(item.text ?? item.transcript ?? item.preview ?? item.event_type ?? JSON.stringify(item));
}

export function TranscriptPanel({ session }: { session: CompanionVoiceSessionBundle | null }) {
  const turns = session?.turns ?? [];
  const partials = session?.stt_events ?? [];

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Captions size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Transcript</h2>
          <p>Text transcript records only. This panel does not capture microphone audio.</p>
        </div>
      </div>

      {!session ? <div className="domain-inline-empty">No voice session selected.</div> : (
        <div className="domain-list">
          {[...turns, ...partials].length === 0 ? (
            <div className="domain-inline-empty">No transcript or STT events recorded.</div>
          ) : [...turns, ...partials].map((item, index) => (
            <div key={`${session.id}-${index}`} className="glass-soft domain-list-card">
              <div className="domain-list-head">
                <strong>{String(item.kind ?? item.event_type ?? "voice event")}</strong>
                <span className="pill-sm">{String(item.status ?? "recorded")}</span>
              </div>
              <p className="domain-card-copy">{preview(item)}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
