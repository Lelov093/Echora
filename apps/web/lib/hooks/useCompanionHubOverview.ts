"use client";

import { useCallback, useEffect, useState } from "react";
import { useCompanionHub } from "@/lib/hooks/useCompanionHub";
import { getLatestContinuity, type ContinuitySnapshot } from "@/lib/api/continuity";
import { getMemoryTimeline, type TimelineEvent } from "@/lib/api/memoryTimeline";
import { listFeedbackEvents, type FeedbackEvent } from "@/lib/api/feedback";
import { DEFAULT_COMPANION_ID } from "@/lib/stores/appStore";

export interface CompanionHubOverviewData {
  companion: Record<string, unknown>;
  stats: Record<string, unknown>;
  continuity: ContinuitySnapshot | null;
  recentTimeline: TimelineEvent[];
  recentMemories: Array<Record<string, unknown>>;
  presencePreview: Array<Record<string, unknown>>;
  pendingReviews: Array<Record<string, unknown>>;
  feedbackDigest: FeedbackEvent[];
}

export function useCompanionHubOverview(companionId?: string | null) {
  const scopedCompanionId = companionId ?? DEFAULT_COMPANION_ID;
  const hub = useCompanionHub(scopedCompanionId);
  const [continuity, setContinuity] = useState<ContinuitySnapshot | null>(null);
  const [recentTimeline, setRecentTimeline] = useState<TimelineEvent[]>([]);
  const [feedbackDigest, setFeedbackDigest] = useState<FeedbackEvent[]>([]);
  const [enriching, setEnriching] = useState(false);

  const loadContinuity = useCallback(async () => {
    setEnriching(true);
    try {
      const [contRes, timelineRes, fbRes] = await Promise.allSettled([
        getLatestContinuity(scopedCompanionId),
        getMemoryTimeline(scopedCompanionId),
        listFeedbackEvents({ companion_id: scopedCompanionId, page_size: "10" }),
      ]);

      if (contRes.status === "fulfilled") setContinuity(contRes.value);
      else setContinuity(null);

      if (timelineRes.status === "fulfilled") setRecentTimeline(timelineRes.value.items || []);
      else setRecentTimeline([]);

      if (fbRes.status === "fulfilled") setFeedbackDigest(fbRes.value.items || []);
      else setFeedbackDigest([]);
    } finally {
      setEnriching(false);
    }
  }, [scopedCompanionId]);

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    if (hub.data) {
      loadContinuity();
    }
  }, [hub.data, loadContinuity]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const pendingReviews = continuity?.pending_reviews || [];

  return {
    data: hub.data
      ? ({
          companion: hub.data.companion || {},
          stats: hub.data.stats || {},
          continuity,
          recentTimeline,
          recentMemories: hub.data.recent_memories || [],
          presencePreview: hub.data.presence_preview || [],
          pendingReviews,
          feedbackDigest,
        } as CompanionHubOverviewData)
      : null,
    loading: hub.loading || enriching,
    error: hub.error,
    reload: hub.reload,
  };
}
