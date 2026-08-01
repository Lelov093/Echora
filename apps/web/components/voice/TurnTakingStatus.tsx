"use client";

import { GitBranch, MessageSquareMore } from "lucide-react";
import type { CompanionVoiceSessionBundle, JsonObject } from "@/lib/types";

function eventLabel(event: JsonObject) {
  return String(event.decision ?? event.action ?? event.event_type ?? "turn decision");
}

export function TurnTakingStatus({ session }: { session: CompanionVoiceSessionBundle | null }) {
  const events = session?.turn_taking_events ?? [];
  const interruptions = session?.interruptions ?? [];

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><GitBranch size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Turn Taking</h2>
          <p>Tracks speak/listen decisions and interruption boundaries.</p>
        </div>
      </div>

      {!session ? <div className="domain-inline-empty">No voice session selected.</div> : (
        <>
          <div className="domain-metric-row">
            <span className="pill-sm">turns {events.length}</span>
            <span className="pill-sm">interruptions {interruptions.length}</span>
            <span className="pill-sm">multi speaker {String(session.allow_multi_speaker)}</span>
          </div>

          <div className="domain-list">
            {events.length === 0 ? (
              <div className="domain-inline-empty">No turn-taking decisions recorded.</div>
            ) : events.map((event, index) => (
              <div key={`${session.id}-turn-${index}`} className="glass-soft domain-list-card">
                <div className="domain-inline-row">
                  <MessageSquareMore size={14} strokeWidth={1.8} />
                  <strong>{eventLabel(event)}</strong>
                </div>
                <pre className="domain-code-block">{JSON.stringify(event, null, 2)}</pre>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
