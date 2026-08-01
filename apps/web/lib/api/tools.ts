import { api, queryString, type QueryParams } from "./client";
import type { PaginatedItems, ToolDefinition } from "@/lib/types";

export type ToolRunStatus =
  | "planned" | "awaiting_input" | "awaiting_confirmation" | "queued" | "running"
  | "retry_scheduled" | "succeeded" | "failed" | "cancelled" | "blocked" | "timed_out";

export interface ToolRun {
  id: string;
  user_id: string;
  companion_id: string;
  conversation_id?: string | null;
  tool_definition_id?: string | null;
  parent_tool_run_id?: string | null;
  requested_by?: string | null;
  trace_run_id?: string | null;
  capability?: string | null;
  status: ToolRunStatus;
  risk_level: string;
  permission_required: boolean;
  permission_granted: boolean;
  confirmation_required: boolean;
  confirmation_summary?: string | null;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  error_json: Record<string, unknown>;
  evidence_refs: Array<Record<string, unknown>>;
  attempt_count: number;
  max_attempts: number;
  timeout_seconds: number;
  terminal_reason?: string | null;
  request_message_id?: string | null;
  result_message_id?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  elapsed_ms?: number | null;
}

export type ToolPermissionPolicy = "not_required" | "ask_once" | "ask_every_time" | "disabled";

export interface ToolPermission {
  id: string;
  user_id: string;
  companion_id: string;
  tool_definition_id: string;
  policy: ToolPermissionPolicy;
  status: "active" | "denied" | "revoked" | "expired";
  allowed_until?: string | null;
  reason?: string | null;
  scope_json?: Record<string, unknown>;
}

export interface ToolRunActionScope {
  companion_id: string;
  conversation_id?: string | null;
  reason?: string;
}

export interface ToolResource {
  id: string;
  companion_id: string;
  conversation_id?: string | null;
  resource_type: "reminder" | "calendar_event" | "note";
  title: string;
  content?: string | null;
  status: "active" | "completed" | "cancelled" | "archived";
  starts_at?: string | null;
  due_at?: string | null;
  timezone?: string | null;
  resource_json: Record<string, unknown>;
  created_at?: string | null;
}

export function listToolDefinitions(params?: QueryParams) {
  return api.get<PaginatedItems<ToolDefinition>>(`/tool-definitions${queryString(params)}`);
}

export function getToolDefinition(id: string) {
  return api.get<ToolDefinition>(`/tool-definitions/${id}`);
}

export function listToolPermissions(params: QueryParams & { companion_id: string }) {
  return api.get<PaginatedItems<ToolPermission>>(`/tool-permissions${queryString(params)}`);
}

export function updateToolPermission(
  id: string,
  data: { companion_id: string; policy?: ToolPermissionPolicy; status?: ToolPermission["status"]; allowed_until?: string | null; reason?: string; scope_json?: Record<string, unknown> },
) {
  return api.patch<ToolPermission>(`/tool-permissions/${id}`, data);
}

export function setToolPermission(
  toolDefinitionId: string,
  data: { companion_id: string; policy: ToolPermissionPolicy; reason?: string },
) {
  return api.put<ToolPermission>(`/tool-permissions/by-definition/${toolDefinitionId}`, data);
}

export function listToolRuns(params: QueryParams & { companion_id: string }) {
  return api.get<PaginatedItems<ToolRun>>(`/tool-runs${queryString(params)}`);
}

export function getToolRun(id: string, companionId: string) {
  return api.get<ToolRun>(`/tool-runs/${id}${queryString({ companion_id: companionId })}`);
}

export function confirmToolRun(id: string, scope: ToolRunActionScope) {
  return api.post<ToolRun>(`/tool-runs/${id}/confirm`, scope);
}

export function cancelToolRun(id: string, scope: ToolRunActionScope) {
  return api.post<ToolRun>(`/tool-runs/${id}/cancel`, scope);
}

export function retryToolRun(id: string, scope: ToolRunActionScope) {
  return api.post<ToolRun>(`/tool-runs/${id}/retry`, scope);
}

export function createToolRunBadCase(id: string, scope: ToolRunActionScope) {
  return api.post(`/tool-runs/${id}/create-bad-case`, scope);
}

export function listToolResources(params: QueryParams & { companion_id: string }) {
  return api.get<ToolResource[]>(`/tool-resources${queryString(params)}`);
}
