import { api } from "./client";

export interface BoundarySettings {
  id: string;
  user_id?: string;
  companion_id?: string;
  memory_save_policy: string | null;
  sensitive_memory_policy: string | null;
  proactive_level: string;
  notification_surface: string;
  allow_auto_memory_low_risk: boolean;
  allow_proactive_presence: boolean;
  allow_sensitive_memory_without_review: boolean;
  suppressed_presence_types: string[];
  // Extended product fields
  quiet_hours?: Record<string, unknown>;
  suppressed_presence_rules?: Array<Record<string, unknown>>;
  memory_confirmation_policy?: Record<string, unknown>;
  growth_confirmation_policy?: Record<string, unknown>;
  feedback_usage_policy?: Record<string, unknown>;
  continuity_visibility_policy?: Record<string, unknown>;
  max_presence_per_day?: number | null;
  min_presence_interval_minutes?: number | null;
  meaningful_silence_enabled?: boolean;
  [key: string]: unknown;
}

export function getSettings(companionId: string) {
  return api.get<BoundarySettings | null>(`/companions/${companionId}/presence-policy`);
}
export function updateSettings(companionId: string, data: Record<string, unknown>) {
  return api.patch<BoundarySettings>(`/companions/${companionId}/presence-policy`, data);
}

export type GovernanceMode = "full_auto" | "partial_auto" | "manual";
export type GovernanceDomainOverride = "inherit" | "automatic" | "manual";

export interface GovernanceDomainPolicy {
  key: "memory" | "growth" | "relationship" | "affect" | "presence" | "tools" | "channels" | "shared" | "quality";
  label: string;
  automation_support: string;
  automatic_available: boolean;
  manual_required_for: string[];
  override: GovernanceDomainOverride;
  requested_mode: "automatic" | "manual";
  effective_mode: "automatic" | "automatic_feedback" | "manual";
  support_status: "supported" | "partial_support" | "not_yet_supported";
}

export interface QualityFeedbackRun {
  id: string;
  source_trace_run_id: string | null;
  source_domain: "quality" | "presence" | "tools" | "channels" | "shared";
  source_entity_type: string;
  source_entity_id: string | null;
  source_entity_revision: number;
  feedback_revision: number;
  trigger_type: string | null;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  aggregate_score: number | null;
  attempt_count: number;
  max_attempts: number;
  result_summary: Record<string, unknown>;
  error: Record<string, unknown>;
  created_at: string | null;
  completed_at: string | null;
}

export interface QualityFeedbackOverview {
  contract_version: string;
  companion_id: string;
  scheduler: { enabled: boolean; poll_seconds: number; lease_seconds: number; lookback_minutes: number };
  run_counts: Record<QualityFeedbackRun["status"], number>;
  domain_counts: Record<string, number>;
  bad_case_counts: Record<string, number>;
  latest_runs: QualityFeedbackRun[];
  claim_boundaries: {
    automatic_detection: boolean;
    automatic_suggestion: boolean;
    automatic_domain_application: boolean;
    raw_prompt_or_message_copied: boolean;
  };
}

export interface GovernancePolicy {
  contract_version: string;
  companion_id: string;
  revision: number;
  mode: GovernanceMode;
  domain_overrides: Record<GovernanceDomainPolicy["key"], GovernanceDomainOverride>;
  domains: GovernanceDomainPolicy[];
  safety_invariants: string[];
  history_count: number;
  can_rollback: boolean;
  updated_at: string | null;
  learned_policy_status: {
    memory_reranker: "shadow";
    contextual_presence_bandit: "shadow";
  };
}

export function getGovernancePolicy(companionId: string) {
  return api.get<GovernancePolicy>(`/companions/${companionId}/governance-policy`);
}

export function updateGovernancePolicy(
  companionId: string,
  data: {
    mode: GovernanceMode;
    domain_overrides: Partial<Record<GovernanceDomainPolicy["key"], GovernanceDomainOverride>>;
    expected_revision: number;
  },
) {
  return api.patch<GovernancePolicy>(`/companions/${companionId}/governance-policy`, data);
}

export function rollbackGovernancePolicy(companionId: string, expectedRevision: number) {
  return api.post<GovernancePolicy>(`/companions/${companionId}/governance-policy/rollback`, {
    expected_revision: expectedRevision,
  });
}

export function getQualityFeedbackOverview(companionId: string) {
  return api.get<QualityFeedbackOverview>(`/companions/${companionId}/quality-feedback`);
}

export function retestQualityFeedback(
  companionId: string,
  runId: string,
  data: { expected_feedback_revision: number; reason: string },
) {
  return api.post<QualityFeedbackRun>(
    `/companions/${companionId}/quality-feedback/${runId}/retest`,
    data,
  );
}

export interface MemorySelectionPolicy {
  contract_version: string;
  companion_id: string;
  revision: number;
  opt_in: boolean;
  requested_mode: "shadow" | "assistive";
  status: "shadow" | "assistive" | "heuristic_fallback";
  effective_mode: "heuristic" | "assistive";
  block_reason: string | null;
  readiness: {
    eligible: boolean;
    block_reason: string | null;
    readiness_status: string;
    readiness_run_id: string | null;
    model_run_id: string | null;
    model_version: string | null;
    model_ready: boolean;
    feature_schema_compatible: boolean;
    assistive_policy_review_allowed: boolean;
  };
  model_run_id: string | null;
  model_version: string | null;
  rollback_available: boolean;
  active_allowed: false;
}

export function getMemorySelectionPolicy(companionId: string) {
  return api.get<MemorySelectionPolicy>(
    `/companions/${companionId}/memory-selection-policy`,
  );
}

export function updateMemorySelectionPolicy(
  companionId: string,
  enabled: boolean,
  expectedRevision: number,
) {
  return api.put<MemorySelectionPolicy>(
    `/companions/${companionId}/memory-selection-policy`,
    { enabled, expected_revision: expectedRevision },
  );
}

export function rollbackMemorySelectionPolicy(
  companionId: string,
  expectedRevision: number,
) {
  return api.post<MemorySelectionPolicy>(
    `/companions/${companionId}/memory-selection-policy/rollback`,
    { expected_revision: expectedRevision },
  );
}

export type PresencePolicySurface = "queue" | "hub";

export interface PresenceTimingPolicy {
  contract_version: string;
  companion_id: string;
  surface: PresencePolicySurface;
  revision: number;
  opt_in: boolean;
  requested_mode: "shadow" | "assistive";
  status: "shadow" | "assistive" | "heuristic_fallback";
  effective_mode: "heuristic" | "assistive";
  block_reason: string | null;
  readiness: {
    eligible: boolean;
    block_reason: string | null;
    readiness_status: string;
    readiness_run_id: string | null;
    algorithm_version: string;
    feature_schema: string[];
    shadow_policy_ready: boolean;
    presence_policy_review_allowed: boolean;
    overall_gate_status: string;
  };
  algorithm_version: string | null;
  rollback_available: boolean;
  active_allowed: false;
  random_user_exploration_allowed: false;
  channel_outbound_allowed: false;
}

export function getPresenceTimingPolicy(
  companionId: string,
  surface: PresencePolicySurface,
) {
  return api.get<PresenceTimingPolicy>(
    `/companions/${companionId}/presence-timing-policy?surface=${surface}`,
  );
}

export function updatePresenceTimingPolicy(
  companionId: string,
  surface: PresencePolicySurface,
  enabled: boolean,
  expectedRevision: number,
) {
  return api.put<PresenceTimingPolicy>(
    `/companions/${companionId}/presence-timing-policy`,
    { surface, enabled, expected_revision: expectedRevision },
  );
}

export function rollbackPresenceTimingPolicy(
  companionId: string,
  surface: PresencePolicySurface,
  expectedRevision: number,
) {
  return api.post<PresenceTimingPolicy>(
    `/companions/${companionId}/presence-timing-policy/rollback`,
    { surface, expected_revision: expectedRevision },
  );
}
