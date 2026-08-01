"use client";

import { Clock, GitBranch, RefreshCw, Trash2 } from "lucide-react";
import { useMemoryTimeline } from "@/lib/hooks/useMemoryTimeline";
import type { TimelineEvent, UsageEvent, LifecycleEvent } from "@/lib/api/memoryTimeline";
import { DataState } from "@/components/patterns/DataState";

interface Props {
  memoryId: string | null;
}

export function MemoryTimelinePanel({ memoryId }: Props) {
  const { data, loading, error } = useMemoryTimeline(memoryId);

  if (!memoryId) {
    return <DataState kind="empty" title="Select a memory" description="Choose a committed memory to inspect its event timeline." />;
  }

  if (loading) {
    return <DataState kind="loading" title="Loading memory timeline" />;
  }

  if (error) {
    return <DataState kind="error" title="Memory timeline unavailable" description={error} />;
  }

  const allItems = [
    ...(data?.timeline || []).map((t: TimelineEvent) => ({
      ...t,
      _kind: "timeline" as const,
    })),
    ...(data?.usage || []).map((u: UsageEvent) => ({
      id: u.id,
      memory_id: u.memory_id || "",
      event_type: u.event_type,
      summary: u.summary,
      created_at: u.created_at,
      _kind: "usage" as const,
    })),
    ...(data?.lifecycle || []).map((l: LifecycleEvent) => ({
      id: l.id,
      memory_id: l.memory_id || "",
      event_type: l.event_type,
      summary: l.reason,
      created_at: l.created_at,
      _kind: "lifecycle" as const,
    })),
  ].sort((a, b) => {
    const da = a.created_at ? new Date(a.created_at).getTime() : 0;
    const db = b.created_at ? new Date(b.created_at).getTime() : 0;
    return db - da;
  });

  const eventIcon = (kind: string) => {
    switch (kind) {
      case "timeline":
        return <GitBranch size={13} strokeWidth={1.7} className="orbital-detail-accent-icon" />;
      case "usage":
        return <RefreshCw size={13} strokeWidth={1.7} className="orbital-detail-success-icon" />;
      case "lifecycle":
        return <Trash2 size={13} strokeWidth={1.7} className="orbital-detail-muted-icon" />;
      default:
        return <Clock size={13} strokeWidth={1.7} className="orbital-detail-muted-icon" />;
    }
  };

  return (
    <div className="glass-soft p-5 rounded-[24px]">
      <div className="flex items-center gap-2 mb-3">
        <Clock size={16} strokeWidth={1.8} className="orbital-detail-accent-icon" />
        <h3 className="text-sm font-semibold orbital-detail-heading">
          Timeline
        </h3>
      </div>

      {allItems.length === 0 ? (
        <p className="text-sm py-4 text-center orbital-detail-label">
          No timeline events recorded yet.
        </p>
      ) : (
        <div className="flex flex-col gap-0 pl-2">
          {allItems.slice(0, 20).map((item, idx) => (
            <div
              key={`${item._kind}-${item.id}-${idx}`}
              className="flex items-start gap-2.5 py-1.5 relative"
            >
              {/* Vertical line */}
              {idx < allItems.length - 1 && idx < 19 && (
                <div
                  className="absolute left-[6px] top-[22px] bottom-0 w-px orbital-detail-timeline-line"
                />
              )}
              {/* Dot */}
              <div className="flex-shrink-0 mt-0.5">{eventIcon(item._kind)}</div>
              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className="orbital-detail-event-chip"
                  >
                    {item.event_type}
                  </span>
                  <span
                    className="orbital-detail-label"
                  >
                    {item._kind}
                  </span>
                </div>
                {item.summary && (
                  <p
                    className="orbital-detail-event-summary"
                  >
                    {item.summary.slice(0, 180)}
                  </p>
                )}
                {item.created_at && (
                  <p className="orbital-detail-event-date">
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                )}
              </div>
            </div>
          ))}
          {allItems.length > 20 && (
            <p className="orbital-detail-label py-2 text-center">
              +{allItems.length - 20} more events
            </p>
          )}
        </div>
      )}
    </div>
  );
}
