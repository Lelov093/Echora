"use client";

import { useState } from "react";
import type { SharedMemoryCandidate } from "@/lib/types";

export function SharedMemoryCandidatePanel({
  items,
  onApprove,
  onReject,
}: {
  items: SharedMemoryCandidate[];
  onApprove: (candidateId: string) => Promise<unknown>;
  onReject: (candidateId: string) => Promise<unknown>;
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
          <h2>SharedMemoryCandidatePanel</h2>
          <p>Shared episodic memory 默认进入 candidate/review，而不是直接写进所有 companion 私有记忆。</p>
        </div>
      </div>

      <div className="domain-list">
        {items.length > 0 ? items.map((item) => (
          <div key={item.id} className="glass-soft domain-list-card">
            <div className="domain-list-head">
              <div>
                <strong>{item.title || "Shared memory candidate"}</strong>
                <div className="domain-list-sub">{item.candidate_status}</div>
              </div>
              <span className="pill-sm">{item.requires_user_review ? "review" : "direct"}</span>
            </div>
            <p className="domain-card-copy">{item.summary}</p>
            <div className="domain-action-row">
              <button className="act-btn act-btn-primary" disabled={!!pending[item.id]} onClick={() => act(item.id, () => onApprove(item.id))}>Approve</button>
              <button className="act-btn" disabled={!!pending[item.id]} onClick={() => act(item.id, () => onReject(item.id))}>Reject</button>
            </div>
          </div>
        )) : <div className="domain-inline-empty">No shared memory candidates.</div>}
      </div>
    </section>
  );
}
