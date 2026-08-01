import { api } from "./client";

export interface FeedbackEvent {
  id: string;
  user_id: string;
  companion_id: string;
  conversation_id?: string | null;
  message_id?: string | null;
  trace_run_id?: string | null;
  target_type: string;
  target_id?: string | null;
  action: string;
  label: string;
  reason?: string | null;
  user_note?: string | null;
  score_delta: number;
  confidence_delta: number;
  strength_delta: number;
  priority_delta: number;
  applies_to_memory: boolean;
  applies_to_growth: boolean;
  applies_to_presence: boolean;
  applies_to_retrieval: boolean;
  applies_to_relationship: boolean;
  applies_to_boundary: boolean;
  calibration_status: string;
  applied_at?: string | null;
  effects?: Array<Record<string, unknown>>;
  created_at?: string | null;
}

export function createFeedbackEvent(data: Record<string, unknown>) {
  return api.post<FeedbackEvent>("/feedback-events", data);
}

export function listFeedbackEvents(params?: Record<string, string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<{ items: FeedbackEvent[]; total: number }>(`/feedback-events${qs}`);
}

export function applyFeedbackEvent(feedbackEventId: string) {
  return api.post<FeedbackEvent>(`/feedback-events/${feedbackEventId}/apply`);
}
