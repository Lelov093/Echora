"use client";

import { useState } from "react";
import type { CrossCompanionMemoryReview } from "@/lib/types";

export function CrossCompanionReviewPanel({
  items,
  onApprove,
  onReject,
}: {
  items: CrossCompanionMemoryReview[];
  onApprove: (reviewId: string) => Promise<unknown>;
  onReject: (reviewId: string) => Promise<unknown>;
}) {
  const [pending, setPending] = useState<Record<string, boolean>>({});

  async function act(id: string, task: () => Promise<unknown>) {
    setPending((current) => ({ ...current, [id]: true }));
    try {
      await task();
    } finally {
      setPending((current) => ({ ...current, [id]: false }));
    }
  }

  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon">X</div>
        <div>
          <h2>CrossCompanionReviewPanel</h2>
          <p>Companion private memory 默认不可跨 companion 读取，高影响共享必须显式 review。</p>
        </div>
      </div>

      <div className="domain-list">
        {items.length > 0 ? items.map((item) => (
          <div key={item.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{item.decision}</strong>
                <div className="domain-list-sub">{item.cross_companion_memory_event_id.slice(0, 8)}</div>
              </div>
            </div>
            <p className="domain-card-copy">{item.review_reason || "No review reason recorded."}</p>
            <div className="domain-action-row">
              <button className="act-btn act-btn-primary" disabled={!!pending[item.id]} onClick={() => act(item.id, () => onApprove(item.id))}>Approve</button>
              <button className="act-btn" disabled={!!pending[item.id]} onClick={() => act(item.id, () => onReject(item.id))}>Reject</button>
            </div>
          </div>
        )) : <div className="domain-inline-empty">No cross-companion reviews.</div>}
      </div>
    </section>
  );
}
