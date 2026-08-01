"use client";

import { Brain, Clock, FilePlus2, RefreshCw, TimerOff } from "lucide-react";
import type { RealtimeMemoryBufferBundle } from "@/lib/types";

interface Props {
  buffer: RealtimeMemoryBufferBundle | null;
  loading?: boolean;
  error?: string | null;
  onCreate?: () => Promise<void>;
  onAppend?: () => Promise<void>;
  onExpire?: () => Promise<void>;
  onReload?: () => void;
  busy?: boolean;
}

export function RealtimeMemoryBufferPanel({ buffer, loading, error, onCreate, onAppend, onExpire, onReload, busy }: Props) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><Brain size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Realtime Memory Buffer</h2>
          <p>Ephemeral working memory for live sessions. It is not long-term memory.</p>
        </div>
      </div>

      <div className="domain-action-row">
        <button className="act-btn" onClick={onCreate} disabled={!onCreate || busy}>
          <FilePlus2 size={14} /> Create buffer
        </button>
        <button className="act-btn glass-btn-secondary" onClick={onAppend} disabled={!buffer || busy}>
          Add sample item
        </button>
        <button className="act-btn glass-btn-secondary" onClick={onExpire} disabled={!buffer || busy}>
          <TimerOff size={14} /> Expire items
        </button>
        <button className="act-btn glass-btn-secondary" onClick={onReload} disabled={!buffer}>
          <RefreshCw size={14} /> Reload
        </button>
      </div>

      {loading && <div className="domain-inline-empty">Realtime buffer is loading...</div>}
      {error && <div className="domain-linked-note">{error}</div>}

      {!buffer ? (
        <div className="domain-inline-empty">No realtime memory buffer selected. Create one from a realtime session.</div>
      ) : (
        <div className="domain-list">
          <div className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{buffer.buffer_scope}</strong>
                <div className="domain-list-sub">{buffer.buffer_status} · {buffer.id.slice(0, 8)}</div>
              </div>
              <span className="pill-sm">{buffer.retention_policy}</span>
            </div>
            <div className="domain-chip-row">
              <span className="pill-sm">review required {String(buffer.review_required)}</span>
              <span className="pill-sm">private auto-write {String(buffer.auto_write_private_memory)}</span>
              <span className="pill-sm">shared auto-write {String(buffer.auto_write_shared_memory)}</span>
            </div>
            {buffer.buffer_summary && <p className="domain-card-copy">{buffer.buffer_summary}</p>}
          </div>

          <div className="glass-soft domain-list-card">
            <div className="domain-inline-row">
              <Clock size={14} strokeWidth={1.8} />
              <strong>Policy snapshot</strong>
            </div>
            <pre className="domain-code-block">{JSON.stringify(buffer.policy_snapshot_json, null, 2)}</pre>
          </div>
        </div>
      )}
    </section>
  );
}
