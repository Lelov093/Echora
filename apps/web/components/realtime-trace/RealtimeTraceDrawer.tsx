"use client";

import { Route, Search } from "lucide-react";
import type { RealtimeTraceV5Detail } from "@/lib/types";

export function RealtimeTraceDrawer({
  trace,
  loading,
  error,
  traceRunId,
  onTraceRunIdChange,
  onReload,
}: {
  trace: RealtimeTraceV5Detail | null;
  loading?: boolean;
  error?: string | null;
  traceRunId: string;
  onTraceRunIdChange: (value: string) => void;
  onReload?: () => void;
}) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Route size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Realtime Trace</h2>
          <p>Readable trace summary, permission audits, memory gates, and hard-stop audit records.</p>
        </div>
      </div>

      <div className="domain-action-row">
        <label
          className="domain-inline-row"
          style={{
            flex: "1 1 320px",
            padding: "0.55rem 0.7rem",
            border: "1px solid rgba(150,185,215,0.24)",
            borderRadius: 10,
            background: "rgba(255,255,255,0.46)",
          }}
        >
          <Search size={14} />
          <input
            value={traceRunId}
            onChange={(event) => onTraceRunIdChange(event.target.value)}
            placeholder="trace_run_id"
            style={{
              width: "100%",
              border: 0,
              outline: 0,
              background: "transparent",
              color: "var(--echora-text-primary)",
            }}
          />
        </label>
        <button className="act-btn" onClick={onReload} disabled={!traceRunId || !onReload}>Load</button>
      </div>

      {loading && <div className="domain-inline-empty">Realtime trace is loading...</div>}
      {error && <div className="domain-linked-note">{error}</div>}

      {!trace ? (
        <div className="domain-inline-empty">Enter a trace_run_id to inspect realtime trace detail.</div>
      ) : (
        <div className="domain-list">
          <div className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <strong>Summary</strong>
              <span className="pill-sm">events {trace.events.length}</span>
            </div>
            <pre className="domain-code-block">{JSON.stringify(trace.summary, null, 2)}</pre>
          </div>
          <div className="domain-mini-grid">
            <div className="glass-soft domain-list-card">Permission audits: {trace.permission_audits.length}</div>
            <div className="glass-soft domain-list-card">Memory gates: {trace.memory_gate_traces.length}</div>
            <div className="glass-soft domain-list-card">Speaker traces: {trace.speaker_traces.length}</div>
            <div className="glass-soft domain-list-card">Hard-stop audits: {trace.hard_stop_audits.length}</div>
          </div>
        </div>
      )}
    </section>
  );
}
