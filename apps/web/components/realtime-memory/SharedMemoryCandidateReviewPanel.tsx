"use client";

import { ShieldCheck } from "lucide-react";
import type { JsonObject } from "@/lib/types";

export function SharedMemoryCandidateReviewPanel({
  salientMoment,
  candidate,
  onCreateCandidate,
}: {
  salientMoment: JsonObject | null;
  candidate: JsonObject | null;
  onCreateCandidate?: () => Promise<void>;
}) {
  return (
    <section className="dynamic-glass domain-panel">
      <div className="domain-panel-header">
        <div className="domain-panel-icon"><ShieldCheck size={16} strokeWidth={1.8} /></div>
        <div>
          <h2>Shared Memory Candidate Review</h2>
          <p>Review gate is mandatory. Candidate records are not written into long-term memory here.</p>
        </div>
      </div>

      <div className="domain-linked-note">
        Default policy: realtime salient moments enter candidate/review. Private or shared long-term writes remain blocked until approval.
      </div>

      <div className="domain-action-row">
        <button className="act-btn" onClick={onCreateCandidate} disabled={!salientMoment || !onCreateCandidate}>
          Create review candidate
        </button>
      </div>

      <div className="domain-mini-grid">
        <div>
          <div className="domain-detail-label">Latest salient moment</div>
          <pre className="domain-code-block">{JSON.stringify(salientMoment ?? {}, null, 2)}</pre>
        </div>
        <div>
          <div className="domain-detail-label">Latest review candidate</div>
          <pre className="domain-code-block">{JSON.stringify(candidate ?? {}, null, 2)}</pre>
        </div>
      </div>
    </section>
  );
}
