import { api } from "./client";

export interface ImpactOverview {
  strength: number;
  confidence: number;
  feedback_score: number;
  used_in_responses: number;
  used_in_growth: number;
  used_in_presence: number;
}

export interface RecentUsage {
  trace_run_id?: string | null;
  used_at?: string | null;
  context?: string | null;
}

export interface GrowthImpact {
  growth_candidate_id?: string | null;
  growth_type?: string | null;
  contribution?: string | null;
  created_at?: string | null;
}

export interface PresenceImpact {
  opportunity_id?: string | null;
  presence_type?: string | null;
  contribution?: string | null;
  created_at?: string | null;
}

export interface FeedbackImpact {
  feedback_event_id?: string | null;
  action?: string | null;
  label?: string | null;
  created_at?: string | null;
}

export interface MemoryImpactResponse {
  overview: ImpactOverview;
  recent_usage: RecentUsage[];
  growth_impact: GrowthImpact[];
  presence_impact: PresenceImpact[];
  feedback_events: FeedbackImpact[];
}

export function getMemoryImpact(memoryId: string) {
  return api.get<MemoryImpactResponse>(`/memories/${memoryId}/impact`);
}
