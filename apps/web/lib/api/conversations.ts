/** Conversation & Message API client. */

import { API_BASE, api, queryString, type QueryParams } from "./client";
import type { ToolRun } from "./tools";
import type {
  CoPresenceSessionBundle,
  CompanionBundle,
  JsonObject,
  SharedMemoryCandidate,
  SharedSceneBundle,
  PaginatedItems,
} from "@/lib/types";

export type ReasoningMode = "auto" | "fast" | "thinking" | "deep_thinking";

export interface ConversationBrief {
  id: string; user_id?: string; companion_id?: string; title: string; mode_key: string; status: string;
  current_topic: string | null; current_goal: string | null;
  continuity_state?: Record<string, unknown>;
  retention_mode: "standard" | "temporary";
  cross_session_memory_enabled: boolean;
  history_visible: boolean;
  reasoning_mode: ReasoningMode;
  retention_expires_at?: string | null;
  created_at: string; updated_at: string;
}

export interface MessageBrief {
  id: string; role: string; content: string;
  content_format?: "text" | "plain_text" | "markdown" | string;
  model_provider?: string | null; model_name?: string | null;
  generation_status?: "completed" | "interrupted" | null;
  created_at: string;
  updated_at?: string | null;
  lifecycle?: { withdrawn: boolean; has_corrections: boolean };
}

export interface ConversationMessageEvidence {
  contract_version: "conversation-message-evidence.v1";
  conversation_id: string;
  companion_id: string;
  assistant_message_id: string;
  trace_run_id: string;
  response: {
    status: string;
    generation_status?: string | null;
    provider_mode?: string | null;
    provider_name?: string | null;
    model_name?: string | null;
    elapsed_ms?: number | null;
    provider_timing: { total_ms?: number; time_to_first_token_ms?: number | null; first_token_measurement_status?: string };
  };
  context: {
    conversation: { title: string; mode_key: string; current_topic?: string | null; current_goal?: string | null };
    memories: {
      retrieved_count?: number | null;
      selected_count?: number | null;
      excluded_count?: number | null;
      boundary_exclusion_counts: Record<string, number>;
      policy_mode: "shadow";
      selected: Array<{ id: string; summary: string; updated_at?: string | null }>;
    };
    snapshot: { contract_version?: string | null; availability?: string | null; scope?: string | null; sources: Array<{ source: string; status?: string | null; reason?: string | null }> };
    pack: {
      status: "available" | "unavailable";
      input_summary?: string | null;
      recent_message_count?: number | null;
      included_count: number;
      excluded_count: number;
      sections: Array<{ key: string; label: string; included: boolean; status: "included" | "excluded"; explanation: string; freshness?: string | null }>;
    };
  };
  boundaries: Array<{ key: string; label: string; status: string; outcome: "applied" | "blocked"; allowed?: boolean | null; scope?: string | null; reason?: string | null }>;
  tools: { status: string; reason?: string | null; run_count: number; runs: ToolRun[] };
  activity: { tool_run_ids: string[]; task_run_id?: string | null };
  decisions: { memory_candidates: number; growth_candidates: number; presence_opportunities: number; review_status: string };
  relationship_explanations: Array<{ id: string; dimension: string; title?: string | null; explanation: string }>;
  post_turn: { status: string; contract_version?: string | null; error_count: number; effects: Array<{ effect?: string | null; status?: string | null; elapsed_ms?: number | null }> };
  workflow?: {
    version: "conversation-response-process.v1";
    stages: Array<{
      key: "understand" | "context" | "memory" | "action" | "respond" | "after_response";
      title: string;
      summary: string;
      status: "completed" | "in_progress" | "attention";
    }>;
  };
}

export interface ConversationCreateInput {
  user_id?: string; companion_id: string; title?: string; mode_key?: string;
  retention_mode?: "standard" | "temporary"; cross_session_memory_enabled?: boolean;
  reasoning_mode?: ReasoningMode;
}

export interface ConversationUpdateInput {
  title?: string; mode_key?: string; current_topic?: string; current_goal?: string;
  cross_session_memory_enabled?: boolean;
  reasoning_mode?: ReasoningMode;
}

export interface ConversationDeletionPreview {
  contract_version: "conversation-deletion.v1";
  conversation_id: string;
  companion_id: string;
  title: string;
  status: "archived";
  affected_counts: {
    messages: number;
    memories: number;
    growth: number;
    tool_runs: number;
    task_runs: number;
    channel_bindings: number;
    related_records: number;
  };
  preserved_domains: string[];
  requires_phrase: "永久删除";
}

export interface ConversationDeletionResult {
  contract_version: "conversation-deletion.v1";
  status: "deleted";
  conversation_id: string;
  completed_at: string;
  affected_counts: ConversationDeletionPreview["affected_counts"];
  deleted_counts: Record<string, number>;
  content_disclosure: "counts_and_safe_status_only";
}

export interface RunMemoryCandidate { id: string; content: string; suggested_type?: string; score?: number; status: string; needs_user_confirmation?: boolean }
export interface RunGrowthCandidate { id: string; content?: string; type?: string; confidence?: number; evidence_score?: number; risk_level?: string; status?: string; profile_patch_preview?: Record<string, unknown> }

export interface RunResult {
  conversation: ConversationBrief | null;
  user_message: MessageBrief;
  assistant_message: MessageBrief;
  related_memories: unknown[];
  memory_candidates: RunMemoryCandidate[];
  growth_candidates: RunGrowthCandidate[];
  presence_opportunities: unknown[];
  trace: {
    trace_run_id: string | null;
    agent_graph_status?: string;
    status?: string;
    step_count?: number;
  };
  suggested_next_step: string;
  agent_graph_status: string;
  provider_mode?: string;
  embedding_mode?: string;
  // Continuity fields
  memory_impact_summary?: Record<string, unknown>;
  continuity_snapshot_id?: string | null;
  continuity_summary?: Record<string, unknown>;
  user_state_snapshot_id?: string | null;
  relationship_explanation_ids?: string[];
  review_batch_id?: string | null;
  review_summary?: Record<string, unknown>;
  memory_usage_event_ids?: string[];
  lifecycle_event_ids?: string[];
  warnings?: string[];
  // Agent execution fields
  tool_runs?: ToolRun[];
  file_evidence?: unknown[];
  evidence_sufficiency?: unknown[];
  project_task_updates?: unknown[];
  outdated_memory_flags?: unknown[];
  growth_consistency_checks?: unknown[];
  bad_case_signals?: unknown[];
  evaluation_signals?: unknown[];
  active_companion?: CompanionBundle | null;
  co_present_companions?: CompanionBundle[];
  co_presence_session?: CoPresenceSessionBundle | null;
  participant_awareness?: JsonObject[];
  shared_scene?: SharedSceneBundle | null;
  companion_memory_scope?: JsonObject | null;
  shared_memory_candidates?: SharedMemoryCandidate[];
  cross_companion_memory_reviews?: JsonObject[];
  persona_guard_result?: JsonObject | null;
  delegation_intent?: JsonObject | null;
}

export type ConversationTurnLifecycleStatus =
  | "accepted"
  | "context_preparing"
  | "provider_waiting"
  | "streaming"
  | "response_persisted"
  | "effects_processing"
  | "completed"
  | "failed"
  | "cancellation_requested"
  | "cancelled";

export interface ConversationTurnStatus {
  contract_version: "conversation-turn-runtime.v1";
  trace_run_id: string;
  conversation_id: string;
  companion_id: string;
  idempotency_key: string;
  reasoning_mode: ReasoningMode;
  idempotent_replay?: boolean;
  status: ConversationTurnLifecycleStatus;
  accepted_at: string;
  started_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
  attempt_count: number;
  stage_timings: Array<{ stage: string; started_at: string; completed_at: string; elapsed_ms: number; status: string }>;
  provider_timing: {
    measurement_mode?: string;
    total_ms?: number;
    time_to_first_token_ms?: number | null;
    first_token_measurement_status?: string;
    token_usage?: { prompt_tokens?: number | null; completion_tokens?: number | null; total_tokens?: number | null };
    reasoning_policy?: {
      policy_version?: string;
      requested_mode?: ReasoningMode;
      router_selected_tier?: string | null;
      requested_tier?: string;
      applied_tier?: string;
      override_reason?: string | null;
      parameter_mode?: string;
      enable_thinking?: boolean | null;
      thinking_budget?: number | null;
      reasoning_content_persisted?: false;
    };
  };
  post_turn_job?: {
    contract_version?: string;
    status?: "queued" | "running" | "retry_scheduled" | "effects_completed" | "completed" | "failed";
    attempt_count?: number;
    max_attempts?: number | null;
    queued_at?: string;
    started_at?: string;
    effects_completed_at?: string;
    completed_at?: string;
    next_attempt_at?: string;
    terminal_failure?: { code?: string };
  };
  failure?: { code?: string; step?: string; error_type?: string } | null;
  user_message: MessageBrief;
  assistant_message?: MessageBrief | null;
  result?: RunResult | null;
}

export function listConversations(params?: QueryParams) {
  return api.get<{ items: ConversationBrief[]; pagination?: { page: number; page_size: number; total: number; total_pages: number } }>(`/conversations${queryString(params)}`);
}
export function createConversation(data: ConversationCreateInput) {
  if (!data.user_id) return Promise.reject(new Error("Companion owner is required to create a Conversation"));
  return api.post<ConversationBrief>("/conversations", data);
}
export function getConversation(id: string, companionId: string) { return api.get<ConversationBrief>(`/conversations/${id}?companion_id=${encodeURIComponent(companionId)}`); }
export function updateConversation(id: string, companionId: string, data: ConversationUpdateInput) { return api.patch<ConversationBrief>(`/conversations/${id}?companion_id=${encodeURIComponent(companionId)}`, data); }
export function archiveConversation(id: string, companionId: string) { return api.post<ConversationBrief>(`/conversations/${id}/archive?companion_id=${encodeURIComponent(companionId)}`); }
export function restoreConversation(id: string, companionId: string) { return api.post<ConversationBrief>(`/conversations/${id}/restore?companion_id=${encodeURIComponent(companionId)}`); }
export function previewConversationDeletion(id: string, companionId: string) {
  return api.get<ConversationDeletionPreview>(`/conversations/${id}/deletion-preview?companion_id=${encodeURIComponent(companionId)}`);
}
export function permanentlyDeleteConversation(id: string, companionId: string, confirmationPhrase: "永久删除") {
  return api.delete<ConversationDeletionResult>(
    `/conversations/${id}?companion_id=${encodeURIComponent(companionId)}`,
    { confirmation_phrase: confirmationPhrase },
  );
}
export function listMessages(
  convId: string,
  companionId: string,
  page = 1,
  pageSize = 50,
  order: "asc" | "desc" = "asc",
) {
  return api.get<PaginatedItems<MessageBrief>>(`/conversations/${convId}/messages${queryString({
    companion_id: companionId,
    page,
    page_size: pageSize,
    order,
  })}`);
}
export function getMessage(convId: string, messageId: string, companionId: string) { return api.get<MessageBrief>(`/conversations/${convId}/messages/${messageId}?companion_id=${encodeURIComponent(companionId)}`); }
export function getConversationMessageEvidence(convId: string, messageId: string, companionId: string) { return api.get<ConversationMessageEvidence>(`/conversations/${convId}/messages/${messageId}/evidence?companion_id=${encodeURIComponent(companionId)}`); }
export function createMessage(convId: string, companionId: string, data: { content: string; content_format?: "text" | "markdown" }) { return api.post<MessageBrief>(`/conversations/${convId}/messages?companion_id=${encodeURIComponent(companionId)}`, data); }
export function correctMessage(convId: string, messageId: string, companionId: string, data: { content: string; reason?: string }) { return api.patch<MessageBrief>(`/conversations/${convId}/messages/${messageId}?companion_id=${encodeURIComponent(companionId)}`, data); }
export function withdrawMessage(convId: string, messageId: string, companionId: string, reason?: string) { return api.post<{ id: string; withdrawn: true }>(`/conversations/${convId}/messages/${messageId}/withdraw?companion_id=${encodeURIComponent(companionId)}`, { reason }); }
export function runConversation(convId: string, data: { companion_id: string; content: string; mode_key?: string; idempotency_key?: string }) {
  return api.post<RunResult>(`/conversations/${convId}/run`, data);
}
export function startConversationTurn(convId: string, data: { companion_id: string; content: string; mode_key?: string; reasoning_mode?: ReasoningMode; idempotency_key: string; continuation_of_trace_run_id?: string }) {
  return api.post<ConversationTurnStatus>(`/conversations/${convId}/turns`, data);
}
export function getConversationTurn(convId: string, traceRunId: string, companionId: string) {
  return api.get<ConversationTurnStatus>(`/conversations/${convId}/turns/${traceRunId}?companion_id=${encodeURIComponent(companionId)}`);
}
export function getLatestConversationTurn(convId: string, companionId: string) {
  return api.get<ConversationTurnStatus | null>(`/conversations/${convId}/turns/current?companion_id=${encodeURIComponent(companionId)}`);
}
export function retryConversationProvider(convId: string, traceRunId: string, companionId: string) {
  return api.post<RunResult>(`/conversations/${convId}/turns/${traceRunId}/retry-provider`, { companion_id: companionId });
}
export function cancelConversationTurn(convId: string, traceRunId: string, companionId: string) {
  return api.post<ConversationTurnStatus & { cancellation_accepted: boolean }>(`/conversations/${convId}/turns/${traceRunId}/cancel`, { companion_id: companionId });
}
export function conversationTurnEventUrl(convId: string, traceRunId: string, companionId: string) {
  return `${API_BASE}/conversations/${convId}/turns/${traceRunId}/events?companion_id=${encodeURIComponent(companionId)}`;
}
