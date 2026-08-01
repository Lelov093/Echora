"use client";

import { Activity, Plug, RefreshCw, Send, WifiOff } from "lucide-react";
import { useRealtimeChannel } from "@/lib/hooks/useRealtimeChannel";
import type { RealtimeSessionChannel } from "@/lib/types";

export function RealtimeChannelPanel({ channel }: { channel: RealtimeSessionChannel | null }) {
  const stream = useRealtimeChannel(channel?.id ?? null, { maxEvents: 25 });

  const publishPing = async () => {
    await stream.publish("session.ui_ping", { source: "RealtimeChannelPanel" }, "UI ping");
    await stream.reload();
  };

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Activity size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Realtime Channel</h2>
          <p>SSE state stream only. WebSocket, WebRTC, and audio transport are not enabled here.</p>
        </div>
      </div>

      {!channel ? (
        <div className="domain-inline-empty">No default realtime event channel is available for this session.</div>
      ) : (
        <>
          <div className="domain-list-head">
            <div>
              <strong>{channel.channel_type}</strong>
              <div className="domain-list-sub">
                {channel.channel_status} · {channel.transport_type} · {channel.id.slice(0, 8)}
              </div>
            </div>
            <div className="domain-chip-row">
              <span className="pill-sm">{stream.connected ? "stream connected" : "stream idle"}</span>
              <span className="pill-sm">{channel.can_send_events ? "send allowed" : "send blocked"}</span>
            </div>
          </div>

          <div className="domain-action-row">
            <button className="act-btn" onClick={stream.connect} disabled={!channel.id || stream.connected}>
              <Plug size={14} /> Connect SSE
            </button>
            <button className="act-btn glass-btn-secondary" onClick={stream.close} disabled={!stream.connected}>
              <WifiOff size={14} /> Close
            </button>
            <button className="act-btn glass-btn-secondary" onClick={stream.reload}>
              <RefreshCw size={14} /> Refresh
            </button>
            <button className="act-btn glass-btn-secondary" onClick={publishPing} disabled={!channel.can_send_events}>
              <Send size={14} /> Ping
            </button>
          </div>

          {stream.error && <div className="domain-linked-note">{stream.error}</div>}
          {stream.loading ? <div className="domain-inline-empty">Loading recent channel events...</div> : null}

          <div className="domain-list">
            {stream.events.length === 0 ? (
              <div className="domain-inline-empty">No recent channel events.</div>
            ) : stream.events.map((event) => (
              <div key={event.id} className="glass-soft domain-list-card">
                <div className="domain-list-head">
                  <div>
                    <strong>{event.event_type || event.event}</strong>
                    <div className="domain-list-sub">{event.event_status || "recorded"} · {event.occurred_at || "no timestamp"}</div>
                  </div>
                  <span className="pill-sm">{event.id.slice(0, 8)}</span>
                </div>
                {event.preview && <p className="domain-card-copy">{event.preview}</p>}
                <pre className="domain-code-block">{JSON.stringify(event.payload, null, 2)}</pre>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
