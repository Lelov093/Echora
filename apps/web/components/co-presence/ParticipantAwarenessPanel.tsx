"use client";

import { Eye, MemoryStick, Shield } from "lucide-react";
import type { CoPresenceParticipant } from "@/lib/types";

export function ParticipantAwarenessPanel({ participants }: { participants: CoPresenceParticipant[] }) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Eye size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>ParticipantAwarenessPanel</h2>
          <p>显式展示谁在场、谁旁听、每个参与者的 awareness state 和 memory permission。</p>
        </div>
      </div>

      <div className="domain-list">
        {participants.map((participant) => (
          <div key={participant.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{participant.participant_role}</strong>
                <div className="domain-list-sub">{participant.participant_type} · {participant.join_status}</div>
              </div>
              <div className="domain-chip-row">
                <span className="pill-sm">{participant.visibility_scope}</span>
                {!participant.can_speak && <span className="pill-sm">silent</span>}
                {participant.can_delegate && <span className="pill-sm">delegate</span>}
              </div>
            </div>

            <div className="domain-mini-grid">
              <div>
                <div className="domain-detail-label">Awareness</div>
                {participant.awareness_states.length > 0 ? participant.awareness_states.map((state) => (
                  <div key={state.id} className="domain-inline-row">
                    <Eye size={13} strokeWidth={1.8} />
                    <span>{state.awareness_type}: {state.awareness_level}</span>
                  </div>
                )) : <div className="domain-inline-empty">No awareness states</div>}
              </div>

              <div>
                <div className="domain-detail-label">Memory permission</div>
                {participant.memory_permission ? (
                  <div className="domain-stack">
                    <div className="domain-inline-row">
                      <MemoryStick size={13} strokeWidth={1.8} />
                      <span>{participant.memory_permission.memory_participation_override || "session default"}</span>
                    </div>
                    <div className="domain-inline-row">
                      <Shield size={13} strokeWidth={1.8} />
                      <span>
                        private {String(participant.memory_permission.allow_private_candidate ?? false)} ·
                        shared {String(participant.memory_permission.allow_shared_candidate ?? false)}
                      </span>
                    </div>
                  </div>
                ) : <div className="domain-inline-empty">No memory permission record</div>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
