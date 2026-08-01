"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Clock } from "lucide-react";
import { useCreateFeedbackEvent } from "@/lib/hooks/useFeedbackEvents";

const CID = "87089684-d2e7-4022-9638-251302a93ef4";

interface Props {
  targetType: string;
  targetId: string;
  memoryId?: string | null;
  conversationId?: string | null;
  traceRunId?: string | null;
}

export function FeedbackActionBar({
  targetType,
  targetId,
  memoryId,
  conversationId,
  traceRunId,
}: Props) {
  const { create, loading } = useCreateFeedbackEvent();
  const [submitted, setSubmitted] = useState<string | null>(null);

  const handle = async (action: string, label: string) => {
    setSubmitted(action);
    await create({
      user_id: "user",
      companion_id: CID,
      target_type: targetType,
      target_id: targetId,
      action,
      label,
      conversation_id: conversationId || null,
      message_id: null,
      trace_run_id: traceRunId || null,
      memory_id: memoryId || null,
    });
  };

  const isDisabled = loading || submitted !== null;

  return (
    <div className="flex gap-2 flex-wrap mt-2">
      <button
        disabled={isDisabled}
        onClick={() => handle("helpful", "Helpful")}
        className="glass-btn-secondary px-3 py-1.5 rounded-[12px] text-xs flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
        style={{ fontSize: "0.72rem" }}
      >
        <ThumbsUp size={13} strokeWidth={1.7} />
        <span>{submitted === "helpful" ? "Marked" : "Helpful"}</span>
      </button>

      <button
        disabled={isDisabled}
        onClick={() => handle("not_helpful", "Not Helpful")}
        className="glass-btn-secondary px-3 py-1.5 rounded-[12px] text-xs flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
        style={{ fontSize: "0.72rem" }}
      >
        <ThumbsDown size={13} strokeWidth={1.7} />
        <span>{submitted === "not_helpful" ? "Marked" : "Not Helpful"}</span>
      </button>

      <button
        disabled={isDisabled}
        onClick={() => handle("outdated", "Outdated")}
        className="glass-btn-secondary px-3 py-1.5 rounded-[12px] text-xs flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
        style={{ fontSize: "0.72rem" }}
      >
        <Clock size={13} strokeWidth={1.7} />
        <span>{submitted === "outdated" ? "Marked" : "Outdated"}</span>
      </button>
    </div>
  );
}
