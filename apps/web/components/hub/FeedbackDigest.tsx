"use client";

import { ThumbsUp, ThumbsDown } from "lucide-react";
import type { FeedbackEvent } from "@/lib/api/feedback";

interface Props {
  events: FeedbackEvent[];
}

export function FeedbackDigest({ events }: Props) {
  if (!events || events.length === 0) {
    return null;
  }

  const helpfulCount = events.filter((e) => e.action === "helpful" || e.label === "helpful").length;
  const irrelevantCount = events.filter(
    (e) => e.action === "not_helpful" || e.label === "not_helpful" || e.action === "irrelevant" || e.label === "irrelevant"
  ).length;

  return (
    <div className="glass-soft p-4 rounded-[20px]">
      <div className="flex items-center gap-2 mb-2">
        <ThumbsUp size={16} strokeWidth={1.8} style={{ color: "var(--echora-accent-blue)" }} />
        <span className="text-sm font-semibold" style={{ color: "var(--echora-text-primary)" }}>
          Recent Feedback
        </span>
      </div>

      <div className="flex gap-3 flex-wrap">
        <div className="flex items-center gap-1.5">
          <ThumbsUp size={14} strokeWidth={1.6} style={{ color: "var(--echora-accent-blue)" }} />
          <span className="text-xs" style={{ color: "var(--echora-text-secondary)" }}>
            {helpfulCount} helpful
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <ThumbsDown size={14} strokeWidth={1.6} style={{ color: "var(--echora-text-muted)" }} />
          <span className="text-xs" style={{ color: "var(--echora-text-secondary)" }}>
            {irrelevantCount} not helpful
          </span>
        </div>
        <span className="text-[0.65rem]" style={{ color: "var(--echora-text-muted)" }}>
          ({events.length} total)
        </span>
      </div>
    </div>
  );
}
