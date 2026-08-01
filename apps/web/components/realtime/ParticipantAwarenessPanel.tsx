"use client";

import { Brain, Ear, Eye, Mic, Shield, UserRound } from "lucide-react";
import type { RealtimeCoPresenceParticipant } from "@/lib/types";

function PermissionPill({ enabled, label, icon }: { enabled: boolean; label: string; icon: React.ReactNode }) {
  return (
    <span
      className="pill-sm"
      style={{
        borderColor: enabled ? "rgba(53, 179, 139, 0.32)" : "rgba(190, 83, 83, 0.25)",
        color: enabled ? "var(--echora-accent-teal)" : "var(--echora-text-muted)",
      }}
    >
      {icon}
      {label}: {enabled ? "on" : "off"}
    </span>
  );
}

export function ParticipantAwarenessPanel({ participants }: { participants: RealtimeCoPresenceParticipant[] }) {
  const active = participants.filter((item) => item.participant_status !== "left");

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><UserRound size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Participant Awareness</h2>
          <p>Shows who is present and which live permissions are currently active.</p>
        </div>
      </div>

      <div className="domain-metric-row">
        <span className="pill-sm">present {active.length}</span>
        <span className="pill-sm">can listen {participants.filter((item) => item.can_listen).length}</span>
        <span className="pill-sm">can speak {participants.filter((item) => item.can_speak).length}</span>
        <span className="pill-sm">can remember {participants.filter((item) => item.can_remember).length}</span>
      </div>

      <div className="domain-list">
        {participants.length === 0 ? (
          <div className="domain-inline-empty">No realtime participants have joined this session.</div>
        ) : participants.map((participant) => (
          <div key={participant.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{participant.external_agent_label || participant.participant_role}</strong>
                <div className="domain-list-sub">
                  {participant.participant_type} · {participant.participant_status}
                </div>
              </div>
              <span className="pill-sm">{participant.id.slice(0, 8)}</span>
            </div>

            <div className="domain-chip-row">
              <PermissionPill enabled={participant.can_listen} label="listen" icon={<Ear size={12} />} />
              <PermissionPill enabled={participant.can_speak} label="speak" icon={<Mic size={12} />} />
              <PermissionPill enabled={participant.can_observe} label="observe" icon={<Eye size={12} />} />
              <PermissionPill enabled={participant.can_remember} label="remember" icon={<Brain size={12} />} />
              <PermissionPill enabled={participant.can_receive_transcript} label="transcript" icon={<Shield size={12} />} />
            </div>

            <div className="domain-detail-label">Runtime state</div>
            <pre className="domain-code-block">{JSON.stringify(participant.runtime_state_json, null, 2)}</pre>
          </div>
        ))}
      </div>
    </section>
  );
}
