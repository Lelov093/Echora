import { api } from "./client";

export interface ContinuitySnapshot {
  id?: string;
  conversation_id?: string | null;
  snapshot_type?: string;
  mode_key?: string;
  current_topic?: string | null;
  current_goal?: string | null;
  current_phase?: string | null;
  last_user_intent?: string | null;
  last_assistant_summary?: string | null;
  open_threads: Array<Record<string, unknown>>;
  unresolved_decisions: Array<Record<string, unknown>>;
  pending_reviews: Array<Record<string, unknown>>;
  suggested_next_steps: Array<Record<string, unknown>>;
  relevant_memory_ids?: string[];
  continuity_score?: number;
  freshness_score?: number;
  user_confirmed?: boolean;
  created_at?: string | null;
}

export function getConversationContinuity(conversationId: string) {
  return api.get<ContinuitySnapshot>(`/conversations/${conversationId}/continuity`);
}

export function getLatestContinuity(companionId: string) {
  // Backend does NOT have /continuity/latest — use snapshots with page_size=1
  return api
    .get<{ items: ContinuitySnapshot[]; total: number }>(
      `/continuity/snapshots?companion_id=${encodeURIComponent(companionId)}&page_size=1`
    )
    .then((res) => (res.items?.length ? res.items[0] : null));
}
