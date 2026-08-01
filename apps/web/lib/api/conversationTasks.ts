import { api, queryString } from "./client";

export type ConversationTaskStatus =
  | "draft" | "awaiting_input" | "awaiting_approval" | "ready" | "running"
  | "paused" | "blocked" | "completed" | "cancelled" | "failed";

export interface ConversationTaskStep {
  id: string;
  order: number;
  title: string;
  executor_type: "tool" | "research" | "verify";
  capability?: string | null;
  risk_level: string;
  status: string;
  dependencies: number[];
  confirmation_required: boolean;
  attempt_count: number;
  acceptance_criteria: string[];
  error: Record<string, unknown>;
  evidence_refs: Array<Record<string, unknown>>;
}

export interface ConversationTaskRun {
  id: string;
  companion_id: string;
  conversation_id: string;
  source_message_id: string;
  goal: string;
  status: ConversationTaskStatus;
  acceptance_state: "pending" | "verified" | "rejected" | "not_applicable";
  plan_version: number;
  revision: number;
  current_step_order?: number | null;
  budgets: {
    max_steps: number;
    max_replans: number;
    replan_count: number;
    max_tool_runs: number;
    tool_run_count: number;
    max_tokens: number;
    token_count: number;
  };
  stop_reason?: string | null;
  steps: ConversationTaskStep[];
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  reasoning_content_persisted: false;
}

export function listConversationTasks(
  companionId: string,
  conversationId: string,
) {
  return api.get<ConversationTaskRun[]>(
    `/conversation-tasks${queryString({
      companion_id: companionId,
      conversation_id: conversationId,
    })}`,
  );
}

export function controlConversationTask(
  taskRunId: string,
  action: "pause" | "resume" | "cancel",
  companionId: string,
  conversationId: string,
) {
  return api.post<ConversationTaskRun>(
    `/conversation-tasks/${taskRunId}/${action}${queryString({
      companion_id: companionId,
      conversation_id: conversationId,
    })}`,
  );
}
