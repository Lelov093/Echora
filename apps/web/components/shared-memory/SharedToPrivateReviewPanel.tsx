"use client";

import { useState } from "react";
import type { SharedToPrivateMemoryReview } from "@/lib/types";

export function SharedToPrivateReviewPanel({
  items,
  onApprove,
  onReject,
}: {
  items: SharedToPrivateMemoryReview[];
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
        <div className="domain-panel-icon">S</div>
        <div>
          <h2>SharedToPrivateReviewPanel</h2>
          <p>Shared-to-private 也必须单独授权，批准后才会给目标 companion 写入私有副本。</p>
        </div>
      </div>

      <div className="domain-list">
        {items.length > 0 ? items.map((item) => (
          <div key={item.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{item.decision}</strong>
                <div className="domain-list-sub">{item.shared_memory_id.slice(0, 8)} → {item.target_companion_id.slice(0, 8)}</div>
              </div>
            </div>
            <p className="domain-card-copy">{item.review_reason || "No review reason recorded."}</p>
            <div className="domain-action-row">
              <button className="act-btn act-btn-primary" disabled={!!pending[item.id]} onClick={() => act(item.id, () => onApprove(item.id))}>Approve</button>
              <button className="act-btn" disabled={!!pending[item.id]} onClick={() => act(item.id, () => onReject(item.id))}>Reject</button>
            </div>
          </div>
        )) : <div className="domain-inline-empty">No shared-to-private reviews.</div>}
      </div>
    </section>
  );
}
