"use client";

import { ListRestart } from "lucide-react";
import type { JsonObject, RealtimeTraceV5Detail } from "@/lib/types";

function segmentLabel(segment: JsonObject, index: number) {
  return String(segment.segment_title ?? segment.event_type ?? segment.replay_segment_type ?? `Replay segment ${index + 1}`);
}

export function RealtimeReplayTimeline({ trace }: { trace: RealtimeTraceV5Detail | null }) {
  const segments = trace?.replay_segments ?? [];

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><ListRestart size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Realtime Replay Timeline</h2>
          <p>Replay uses summaries and key events only. Raw audio, screen, and video remain excluded.</p>
        </div>
      </div>

      {!trace ? <div className="domain-inline-empty">Load a realtime trace to view replay detail.</div> : (
        <div className="domain-list">
          <div className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <strong>Replay contract</strong>
              <span className="pill-sm">{trace.replay ? "available" : "not created"}</span>
            </div>
            <pre className="domain-code-block">{JSON.stringify(trace.replay ?? {}, null, 2)}</pre>
          </div>

          {segments.length === 0 ? (
            <div className="domain-inline-empty">No replay segments available.</div>
          ) : segments.map((segment, index) => (
            <div key={String(segment.id ?? index)} className="glass-soft domain-list-card">
              <div className="domain-list-head">
                <strong>{segmentLabel(segment, index)}</strong>
                <span className="pill-sm">{String(segment.redaction_status ?? "redaction_required")}</span>
              </div>
              <pre className="domain-code-block">{JSON.stringify(segment, null, 2)}</pre>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
