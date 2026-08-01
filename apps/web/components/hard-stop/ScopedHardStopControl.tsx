"use client";

import { Ban, OctagonAlert } from "lucide-react";
import { useScopedHardStop } from "@/lib/hooks/useScopedHardStop";

interface Props {
  userId: string;
  sessionId?: string;
  channelId?: string;
  companionId?: string;
  contextEventId?: string;
}

export function ScopedHardStopControl({ userId, sessionId, channelId, companionId, contextEventId }: Props) {
  const hardStop = useScopedHardStop();

  const basePayload = { user_id: userId, reason: "manual_ui_hard_stop", source: "realtime_ui" };

  return (
    <section className="dynamic-glass domain-panel" style={{ borderColor: "rgba(212, 79, 79, 0.32)" }}>
      <div className="domain-panel-header">
        <div className="domain-panel-icon" style={{ color: "rgb(184, 55, 55)" }}>
          <OctagonAlert size={16} strokeWidth={1.9} />
        </div>
        <div>
          <h2>Scoped Hard Stop</h2>
          <p>Immediate stop controls for this session scope. They do not enable background listening.</p>
        </div>
      </div>

      <div className="domain-action-row">
        <button className="act-btn" onClick={() => sessionId && hardStop.stopSession({ ...basePayload, realtime_session_id: sessionId })} disabled={!sessionId || hardStop.saving}>
          <Ban size={14} /> Stop session
        </button>
        <button className="act-btn glass-btn-secondary" onClick={() => channelId && hardStop.stopChannel({ ...basePayload, channel_id: channelId })} disabled={!channelId || hardStop.saving}>
          Stop channel
        </button>
        <button className="act-btn glass-btn-secondary" onClick={() => companionId && hardStop.stopCompanion({ ...basePayload, companion_id: companionId })} disabled={!companionId || hardStop.saving}>
          Stop companion
        </button>
        <button className="act-btn glass-btn-secondary" onClick={() => hardStop.stopSensor({ ...basePayload, context_event_id: contextEventId ?? null, sensor_scope: "manual_context_capture" })} disabled={hardStop.saving}>
          Stop sensor
        </button>
      </div>

      {hardStop.error && <div className="domain-linked-note">{hardStop.error}</div>}
      {hardStop.result && (
        <div className="glass-soft domain-list-card">
          <div className="domain-detail-label">Latest stop audit</div>
          <pre className="domain-code-block">{JSON.stringify(hardStop.result.audit, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
