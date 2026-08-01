"use client";

import { Mic2, RefreshCw, ShieldAlert, Volume2 } from "lucide-react";
import type { CompanionVoiceSessionBundle } from "@/lib/types";

interface Props {
  sessions: CompanionVoiceSessionBundle[];
  selected: CompanionVoiceSessionBundle | null;
  onSelect: (sessionId: string) => void;
  onReload?: () => void;
  onCreate?: () => Promise<void>;
  creating?: boolean;
}

export function CompanionVoicePanel({ sessions, selected, onSelect, onReload, onCreate, creating }: Props) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Mic2 size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Companion Voice</h2>
          <p>Voice-session state, transcript policy, TTS/STT records, and persona guard results.</p>
        </div>
      </div>

      <div className="domain-action-row">
        <button className="act-btn" onClick={onCreate} disabled={!onCreate || creating}>
          <Volume2 size={14} /> Create text voice session
        </button>
        <button className="act-btn glass-btn-secondary" onClick={onReload}>
          <RefreshCw size={14} /> Reload
        </button>
      </div>

      <div className="domain-list">
        {sessions.length === 0 ? (
          <div className="domain-inline-empty">No companion voice sessions yet.</div>
        ) : sessions.map((session) => (
          <button
            key={session.id}
            className="glass-soft domain-list-card text-left"
            onClick={() => onSelect(session.id)}
            style={{ borderColor: selected?.id === session.id ? "rgba(53, 179, 139, 0.45)" : undefined }}
          >
            <div className="domain-list-head">
              <div>
                <strong>{session.session_status}</strong>
                <div className="domain-list-sub">
                  {session.id.slice(0, 8)} · retention {session.transcript_retention_policy}
                </div>
              </div>
              <span className="pill-sm">{session.memory_write_policy}</span>
            </div>
            <div className="domain-inline-row">
              <ShieldAlert size={14} strokeWidth={1.8} />
              <span>persona guard runs {session.persona_guard_runs.length}</span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
