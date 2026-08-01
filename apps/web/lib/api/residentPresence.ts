import { apiPost } from "./client";
import type { CoPresenceInvitationRecord, MeaningfulSilenceResult, PresenceBudgetEvaluation, ResidentStatusRecord } from "@/lib/types";

function normalizeStatus(data: Partial<ResidentStatusRecord> | null): ResidentStatusRecord {
  const item = data ?? {};
  return {
    id: item.id ?? "",
    user_id: item.user_id ?? "",
    companion_id: item.companion_id ?? "",
    realtime_session_id: item.realtime_session_id ?? null,
    status_type: item.status_type ?? "available",
    status_source: item.status_source ?? "user",
    interruption_level: item.interruption_level ?? "low",
    allows_unsolicited_presence: item.allows_unsolicited_presence ?? false,
    presence_summary: item.presence_summary ?? null,
    policy_snapshot_json: item.policy_snapshot_json ?? {},
    occurred_at: item.occurred_at ?? null,
  };
}

function normalizeBudget(data: Partial<PresenceBudgetEvaluation> | null): PresenceBudgetEvaluation {
  const item = data ?? {};
  return {
    id: item.id ?? "",
    user_id: item.user_id ?? "",
    companion_id: item.companion_id ?? "",
    budget_scope: item.budget_scope ?? "day",
    budget_status: item.budget_status ?? "active",
    enforcement_policy: item.enforcement_policy ?? "queue_when_exhausted",
    max_presence_minutes: item.max_presence_minutes ?? 0,
    used_presence_minutes: item.used_presence_minutes ?? 0,
    max_interruptions: item.max_interruptions ?? 0,
    used_interruptions: item.used_interruptions ?? 0,
    budget_policy_json: item.budget_policy_json ?? {},
    decision: item.decision ?? "allowed",
    allowed: item.allowed ?? false,
  };
}

function normalizeInvitation(data: Partial<CoPresenceInvitationRecord> | null): CoPresenceInvitationRecord {
  const item = data ?? {};
  return {
    id: item.id ?? "",
    user_id: item.user_id ?? "",
    realtime_session_id: item.realtime_session_id ?? null,
    inviter_companion_id: item.inviter_companion_id ?? null,
    target_companion_id: item.target_companion_id ?? null,
    invitation_status: item.invitation_status ?? "queued",
    invitation_source: item.invitation_source ?? "user_request",
    requires_user_approval: item.requires_user_approval ?? true,
    auto_join_allowed: item.auto_join_allowed ?? false,
    memory_candidate_allowed: item.memory_candidate_allowed ?? false,
    invitation_reason: item.invitation_reason ?? null,
    policy_snapshot_json: item.policy_snapshot_json ?? {},
    expires_at: item.expires_at ?? null,
  };
}

export function setResidentStatus(data: Record<string, unknown>) {
  return apiPost<ResidentStatusRecord>("/resident-presence/status", data).then(normalizeStatus);
}

export function evaluateResidentPresenceBudget(data: Record<string, unknown>) {
  return apiPost<PresenceBudgetEvaluation>("/resident-presence/budget/evaluate", data).then(normalizeBudget);
}

export function createResidentCoPresenceInvitation(data: Record<string, unknown>) {
  return apiPost<CoPresenceInvitationRecord>("/resident-presence/invitations", data).then(normalizeInvitation);
}

export function applyMeaningfulSilence(data: Record<string, unknown>) {
  return apiPost<MeaningfulSilenceResult>("/resident-presence/meaningful-silence", data).then((result) => ({
    quiet: result?.quiet ?? {},
    focus: result?.focus ?? {},
  }));
}
