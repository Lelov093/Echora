import { api } from "./client";

export interface PresenceOpportunity {
  id: string; type?: string; title?: string; status: string;
  reason?: string; summary?: string; message?: string;
  priority?: number; urgency?: number; sensitivity?: number;
  interruption_risk?: number; recommended_surface?: string;
  // Extended product fields
  snoozed_until?: string | null; dismissed_at?: string | null;
  dismissed_reason?: string | null; accepted_at?: string | null;
  suppress_type_rule_applied?: boolean;
  timing_score?: number; type_affinity_snapshot?: number;
  meaningful_silence_reason?: string | null;
  feedback_label?: string | null; feedback_event_id?: string;
  calibration_json?: Record<string, unknown>;
  opportunity_context_hash?: string;
  created_at?: string;
}

export function listOpportunities(params?: Record<string,string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<{ items: PresenceOpportunity[]; total: number }>(`/presence/opportunities${qs}`);
}
export function acceptOpportunity(id: string) { return api.post(`/presence/opportunities/${id}/accept`); }
export function dismissOpportunity(id: string) { return api.post(`/presence/opportunities/${id}/dismiss`); }
export function snoozeOpportunity(id: string) { return api.post(`/presence/opportunities/${id}/snooze`); }
export function suppressOpportunityType(id: string) { return api.post(`/presence/opportunities/${id}/suppress-type`); }

export type PresenceDestinationMode = "bound_conversation" | "new_conversation_per_delivery";
export interface PresenceSchedule {
  id: string; user_id: string; companion_id: string; status: "active" | "paused";
  pause_reason?: string | null; destination_mode: PresenceDestinationMode;
  bound_conversation_id?: string | null; latest_created_conversation_id?: string | null;
  timezone: string; weekdays: number[]; timing_mode: "fixed" | "random_window";
  fixed_minute_of_day: number; window_start_minute: number; window_end_minute: number;
  cadence_mode: "fixed" | "random_interval"; fixed_interval_minutes: number;
  random_interval_min_minutes: number; random_interval_max_minutes: number;
  revision: number; next_occurrence_at?: string | null; last_delivered_at?: string | null; updated_at: string;
}
export type PresenceScheduleInput = Omit<PresenceSchedule, "id" | "user_id" | "companion_id" | "pause_reason" | "latest_created_conversation_id" | "next_occurrence_at" | "last_delivered_at" | "updated_at" | "revision"> & { expected_revision?: number };
export interface PresenceOccurrence {
  id: string; status: string; sequence_no: number; scheduled_for: string; next_attempt_at?: string | null; delivered_at?: string | null;
  attempt_count: number; conversation_id?: string | null; message_id?: string | null;
  suppression_reason?: string | null; error_code?: string | null;
  random_draw: Record<string, unknown>; delivery_evidence: Record<string, unknown>;
}
export interface PresenceConfigurationVersions {
  schedule_revision: number | null;
  policy_updated_at: string | null;
  persona_updated_at: string;
  boundary_updated_at: string;
}
export interface PresenceConfigurationValue {
  enabled: boolean;
  proactive_level: "low" | "medium" | "high";
  presence_style: "quiet" | "balanced" | "expressive";
  notification_surface: "hub_queue_only" | "allow_light_notification" | "disabled";
  meaningful_silence_enabled: boolean;
  quiet_hours: { enabled: boolean; start: string; end: string };
  max_presence_per_day: number;
  destination_mode: PresenceDestinationMode;
  bound_conversation_id: string | null;
  timezone: string;
  weekdays: number[];
  timing_mode: "fixed" | "random_window";
  fixed_minute_of_day: number;
  window_start_minute: number;
  window_end_minute: number;
  cadence_mode: "fixed" | "random_interval";
  fixed_interval_minutes: number;
  random_interval_min_minutes: number;
  random_interval_max_minutes: number;
}
export interface PresenceConfiguration {
  contract_version: "presence-configuration.v1";
  user_id: string;
  companion_id: string;
  versions: PresenceConfigurationVersions;
  configuration: PresenceConfigurationValue;
  runtime: { next_occurrence_at: string | null; last_delivered_at: string | null };
  consistency: {
    status: "aligned" | "needs_save_to_align";
    warnings: string[];
    canonical_quiet_hours_source: "boundary_settings";
    derived_profile_projection: boolean;
    derived_min_interval_from_schedule: boolean;
  };
}
export type PresenceConfigurationInput = PresenceConfigurationValue & {
  expected_schedule_revision: number | null;
  expected_policy_updated_at: string | null;
  expected_persona_updated_at: string;
  expected_boundary_updated_at: string;
};
export function getPresenceConfiguration(companionId: string, userId: string) {
  return api.get<PresenceConfiguration>(`/companions/${companionId}/presence-configuration?user_id=${encodeURIComponent(userId)}`);
}
export function savePresenceConfiguration(companionId: string, userId: string, input: PresenceConfigurationInput) {
  return api.put<PresenceConfiguration>(`/companions/${companionId}/presence-configuration?user_id=${encodeURIComponent(userId)}`, input);
}
export function getPresenceSchedule(companionId: string, userId: string) {
  return api.get<PresenceSchedule | null>(`/presence/schedules/${companionId}?user_id=${encodeURIComponent(userId)}`);
}
export function savePresenceSchedule(companionId: string, userId: string, input: PresenceScheduleInput) {
  return api.put<PresenceSchedule>(`/presence/schedules/${companionId}?user_id=${encodeURIComponent(userId)}`, input);
}
export function triggerPresenceSchedule(companionId: string, userId: string, expectedRevision: number) {
  return api.post<PresenceOccurrence>(`/presence/schedules/${companionId}/trigger?user_id=${encodeURIComponent(userId)}`, { expected_revision: expectedRevision });
}
export function listPresenceOccurrences(companionId: string, userId: string, limit = 12) {
  return api.get<PresenceOccurrence[]>(`/presence/schedules/${companionId}/occurrences?user_id=${encodeURIComponent(userId)}&limit=${limit}`);
}
