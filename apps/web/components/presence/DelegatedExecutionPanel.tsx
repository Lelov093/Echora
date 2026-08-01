"use client";

import type { DelegatedExecutionIntentRecord } from "@/lib/types";

export function DelegatedExecutionPanel({ items }: { items: DelegatedExecutionIntentRecord[] }) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon">D</div>
        <div>
          <h2>Delegated Execution</h2>
          <p>Delegated execution is assistive. Echora frames intent and reviews results while external agents handle execution.</p>
        </div>
      </div>

      <div className="domain-list">
        {items.length > 0 ? items.map((item) => (
          <div key={item.trace_run_id || item.task_title} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{item.task_title}</strong>
                <div className="domain-list-sub">{item.status} / {item.executor_type || "unassigned"}</div>
              </div>
              <span className="pill-sm">{item.trace_run_id ? item.trace_run_id.slice(0, 8) : "pending"}</span>
            </div>
            <p className="domain-card-copy">{item.task_summary || "Delegated execution intent is waiting for a fuller summary."}</p>
            {item.inspection_summary && <div className="domain-linked-note">{item.inspection_summary}</div>}
          </div>
        )) : <div className="domain-inline-empty">No delegated execution intents.</div>}
      </div>
    </section>
  );
}
