"use client";

import { MessageSquare, Target } from "lucide-react";
import type { ContinuitySnapshot } from "@/lib/api/continuity";

interface Props {
  continuity: ContinuitySnapshot | null;
}

export function ContinuityDigest({ continuity }: Props) {
  if (!continuity) {
    return null;
  }

  const openCount = (continuity.open_threads || []).length;
  const pendingCount = (continuity.pending_reviews || []).length;
  const hasContent = continuity.current_topic || continuity.current_goal;
  if (!hasContent && openCount === 0 && pendingCount === 0) {
    return null;
  }

  return (
    <div className="glass-soft p-4 rounded-[20px]">
      <div className="flex items-center gap-2 mb-2">
        <MessageSquare size={16} strokeWidth={1.8} style={{ color: "var(--echora-accent-blue)" }} />
        <span className="text-sm font-semibold" style={{ color: "var(--echora-text-primary)" }}>
          Continuity Digest
        </span>
      </div>

      {continuity.current_topic && (
        <div className="mb-1.5">
          <span className="text-[0.7rem] uppercase tracking-wider" style={{ color: "var(--echora-text-muted)" }}>
            Current Topic
          </span>
          <p className="text-sm mt-0.5" style={{ color: "var(--echora-text-secondary)", lineHeight: 1.4 }}>
            {continuity.current_topic}
          </p>
        </div>
      )}

      {continuity.current_goal && (
        <div className="mb-1.5">
          <div className="flex items-center gap-1">
            <Target size={12} strokeWidth={1.8} style={{ color: "var(--echora-text-muted)" }} />
            <span className="text-[0.7rem] uppercase tracking-wider" style={{ color: "var(--echora-text-muted)" }}>
              Current Goal
            </span>
          </div>
          <p className="text-sm mt-0.5" style={{ color: "var(--echora-text-secondary)", lineHeight: 1.4 }}>
            {continuity.current_goal}
          </p>
        </div>
      )}

      <div className="flex gap-2 flex-wrap mt-2">
        {openCount > 0 && (
          <span className="pill-sm">
            {openCount} open thread{openCount !== 1 ? "s" : ""}
          </span>
        )}
        {pendingCount > 0 && (
          <span className="pill-sm pill-accent">
            {pendingCount} pending review{pendingCount !== 1 ? "s" : ""}
          </span>
        )}
      </div>
    </div>
  );
}
