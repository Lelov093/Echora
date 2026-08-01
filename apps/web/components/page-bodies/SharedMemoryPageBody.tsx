"use client";

import { useSharedMemory } from "@/lib/hooks/useSharedMemory";
import { SharedMemoryCandidatePanel } from "@/components/shared-memory/SharedMemoryCandidatePanel";
import { CrossCompanionReviewPanel } from "@/components/shared-memory/CrossCompanionReviewPanel";
import { PrivateToSharedReviewPanel } from "@/components/shared-memory/PrivateToSharedReviewPanel";
import { SharedToPrivateReviewPanel } from "@/components/shared-memory/SharedToPrivateReviewPanel";
import { SectionNav } from "@/components/navigation/SectionNav";
import { memoryNavItems } from "@/lib/navigation/routes";

export default function SharedMemoryPageBody() {
  const shared = useSharedMemory({ page_size: 50 });
  const loading =
    shared.memories.loading ||
    shared.candidates.loading ||
    shared.crossReviews.loading ||
    shared.privateToShared.loading ||
    shared.sharedToPrivate.loading;

  return (
    <>
    <SectionNav title="Memory" eyebrow="Private and shared review gates" items={memoryNavItems} />
    <main className="echora-page domain-page">
      <section className="dynamic-glass domain-page-hero">
        <div>
          <div className="domain-chip-row">
            <span className="pill-sm pill-accent">Shared Memory</span>
            <span className="pill-sm">{loading ? "loading" : `${shared.memories.items.length} memories`}</span>
            <span className="pill-sm">{shared.candidates.items.length} candidates</span>
          </div>
          <h1>å±äº«è®°å¿å®¡æ¥é¢æ¿</h1>
          <p>
            Shared episodic memory and cross-Companion writes stay review-first instead of spreading automatically.
          </p>
        </div>
      </section>

      {loading && (
        <section className="glass-soft domain-inline-empty" style={{ marginBottom: "18px" }}>
          Loading shared memory surfaces...
        </section>
      )}

      <div className="domain-three-column">
        <SharedMemoryCandidatePanel
          items={shared.candidates.items}
          onApprove={(id) => shared.decideSharedMemoryCandidate(id, { decision: "approved", review_reason: "Approved from shared memory panel." }).then(shared.reloadAll)}
          onReject={(id) => shared.decideSharedMemoryCandidate(id, { decision: "rejected", review_reason: "Rejected from shared memory panel." }).then(shared.reloadAll)}
        />
        <PrivateToSharedReviewPanel
          items={shared.privateToShared.items}
          onApprove={(id) => shared.decidePrivateToSharedReview(id, { decision: "approved", review_reason: "Approved from private-to-shared panel." }).then(shared.reloadAll)}
          onReject={(id) => shared.decidePrivateToSharedReview(id, { decision: "rejected", review_reason: "Rejected from private-to-shared panel." }).then(shared.reloadAll)}
        />
        <SharedToPrivateReviewPanel
          items={shared.sharedToPrivate.items}
          onApprove={(id) => shared.decideSharedToPrivateReview(id, { decision: "approved", review_reason: "Approved from shared-to-private panel." }).then(shared.reloadAll)}
          onReject={(id) => shared.decideSharedToPrivateReview(id, { decision: "rejected", review_reason: "Rejected from shared-to-private panel." }).then(shared.reloadAll)}
        />
      </div>

      <div className="domain-two-column" style={{ marginTop: "18px" }}>
        <CrossCompanionReviewPanel
          items={shared.crossReviews.items}
          onApprove={(id) => shared.decideCrossCompanionReview(id, {
            decision: "approved",
            review_reason: "Approved from cross-companion review panel.",
            create_shared_to_private_review: true,
          }).then(shared.reloadAll)}
          onReject={(id) => shared.decideCrossCompanionReview(id, {
            decision: "rejected",
            review_reason: "Rejected from cross-companion review panel.",
          }).then(shared.reloadAll)}
        />

        <section className="dynamic-glass domain-panel">
          <div className="domain-panel-header">
            <div className="domain-panel-icon">A</div>
            <div>
              <h2>Approved Shared Memories</h2>
          <p>
            Shared episodic memory and cross-Companion writes stay review-first instead of spreading automatically.
          </p>
            </div>
          </div>
          <div className="domain-list">
            {shared.memories.items.length > 0 ? shared.memories.items.map((item) => (
              <div key={item.id} className="glass-soft domain-list-card">
                <div className="domain-list-head">
                  <div>
                    <strong>{item.title || "Shared memory"}</strong>
                    <div className="domain-list-sub">{item.status} Â· {item.source_type}</div>
                  </div>
                </div>
                <p className="domain-card-copy">{item.summary}</p>
              </div>
            )) : <div className="domain-inline-empty">No approved shared memories.</div>}
          </div>
        </section>
      </div>
    </main>
    </>
  );
}
