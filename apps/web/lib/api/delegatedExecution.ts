import { apiGet, apiPost } from "./client";
import type { DelegatedExecutionIntentRecord, PaginatedItems } from "@/lib/types";

function toQuery(params?: Record<string, string | number | undefined | null>) {
  if (!params) return "";
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "");
  return entries.length > 0 ? `?${new URLSearchParams(entries.map(([key, value]) => [key, String(value)])).toString()}` : "";
}

type RawDelegatedExecutionIntentRecord = {
  id?: string;
  user_id?: string | null;
  companion_id?: string | null;
  conversation_id?: string | null;
  status?: string;
  input_summary?: string | null;
  output_summary?: string | null;
  metadata?: Record<string, unknown>;
};

function normalizeDelegatedExecutionIntent(raw: RawDelegatedExecutionIntentRecord): DelegatedExecutionIntentRecord {
  const metadata = (raw.metadata ?? {}) as Record<string, unknown>;
  const delegation = (metadata.delegation ?? {}) as Record<string, unknown>;
  const linkedExecution = (delegation.linked_execution ?? {}) as Record<string, unknown>;
  const inspection = (delegation.inspection ?? {}) as Record<string, unknown>;

  return {
    trace_run_id: raw.id ?? "",
    conversation_id: raw.conversation_id ?? null,
    user_id: raw.user_id ?? null,
    requested_by_companion_id: (delegation.requested_by_companion_id as string | undefined) ?? raw.companion_id ?? null,
    co_presence_session_id: (delegation.co_presence_session_id as string | undefined) ?? null,
    shared_scene_id: (delegation.shared_scene_id as string | undefined) ?? null,
    task_title: (delegation.task_title as string | undefined) ?? raw.input_summary ?? "Delegated execution intent",
    task_summary: (delegation.task_summary as string | undefined) ?? raw.input_summary ?? "",
    status: raw.status ?? "pending",
    executor_type: (linkedExecution.executor_type as string | undefined)
      ?? (delegation.executor_type as string | undefined)
      ?? null,
    tool_constraints: (delegation.tool_constraints as Record<string, unknown> | undefined) ?? {},
    memory_boundary_json: (delegation.memory_boundary_json as Record<string, unknown> | undefined) ?? {},
    boundary_check: (delegation.boundary_check as Record<string, unknown> | undefined) ?? {},
    linked_tool_run_id: (linkedExecution.tool_run_id as string | undefined) ?? null,
    linked_project_task_id: (linkedExecution.project_task_id as string | undefined) ?? null,
    inspection_summary: (inspection.result_summary as string | undefined)
      ?? raw.output_summary
      ?? (inspection.acceptance_note as string | undefined)
      ?? null,
    shared_experience_record_id: (delegation.shared_experience_record_id as string | undefined) ?? null,
    shared_experience_status: (metadata.shared_experience_status as string | undefined) ?? null,
    created_at: null,
    updated_at: null,
    metadata,
  };
}

function normalizeDelegatedExecutionPage(
  page: PaginatedItems<RawDelegatedExecutionIntentRecord>,
): PaginatedItems<DelegatedExecutionIntentRecord> {
  return {
    ...page,
    items: (page.items ?? []).map(normalizeDelegatedExecutionIntent),
  };
}

export function listDelegatedExecutionIntents(params?: Record<string, string | number | undefined | null>) {
  return apiGet<PaginatedItems<RawDelegatedExecutionIntentRecord>>(`/delegated-executions/intents${toQuery(params)}`)
    .then(normalizeDelegatedExecutionPage);
}

export function createDelegatedExecutionIntent(data: Record<string, unknown>) {
  return apiPost<RawDelegatedExecutionIntentRecord>("/delegated-executions/intents", data)
    .then(normalizeDelegatedExecutionIntent);
}

export function getDelegatedExecutionIntent(traceRunId: string) {
  return apiGet<RawDelegatedExecutionIntentRecord>(`/delegated-executions/intents/${traceRunId}`)
    .then(normalizeDelegatedExecutionIntent);
}

export function linkDelegatedExecution(traceRunId: string, data: Record<string, unknown>) {
  return apiPost<RawDelegatedExecutionIntentRecord>(`/delegated-executions/intents/${traceRunId}/link`, data)
    .then(normalizeDelegatedExecutionIntent);
}

export function inspectDelegatedExecution(traceRunId: string, data: Record<string, unknown>) {
  return apiPost<RawDelegatedExecutionIntentRecord>(`/delegated-executions/intents/${traceRunId}/inspect`, data)
    .then(normalizeDelegatedExecutionIntent);
}

export function createDelegatedSharedExperience(traceRunId: string, data: Record<string, unknown>) {
  return apiPost<{ delegation_intent: RawDelegatedExecutionIntentRecord }>(
    `/delegated-executions/intents/${traceRunId}/shared-experience`,
    data,
  ).then((result) => normalizeDelegatedExecutionIntent(result.delegation_intent));
}
