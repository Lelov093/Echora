import { api, queryString, type QueryParams } from "./client";
import type { LlmProviderConfig, PaginatedItems } from "@/lib/types";

export interface LlmModelConfig {
  id: string;
  provider_config_id?: string | null;
  model_name: string;
  model_role: string;
  status: string;
  temperature?: number | null;
  max_tokens?: number | null;
}

export interface PromptVersion {
  id: string;
  prompt_key: string;
  version: string;
  status: string;
  content: string;
  change_note?: string | null;
}

export interface LlmCallRecord {
  id: string;
  trace_run_id?: string | null;
  status: string;
  purpose: string;
  input_summary?: string | null;
  output_summary?: string | null;
  token_input?: number | null;
  token_output?: number | null;
  fallback_used: boolean;
}

export interface FallbackEvent {
  id: string;
  trace_run_id?: string | null;
  llm_call_record_id?: string | null;
  reason: string;
  status: string;
}

export function listProviderConfigs(params?: QueryParams) {
  return api.get<PaginatedItems<LlmProviderConfig>>(`/llm-provider-configs${queryString(params)}`);
}
export function listModelConfigs(params?: QueryParams) {
  return api.get<PaginatedItems<LlmModelConfig>>(`/llm-model-configs${queryString(params)}`);
}
export function listPromptVersions(params?: QueryParams) {
  return api.get<PaginatedItems<PromptVersion>>(`/prompt-versions${queryString(params)}`);
}
export function createPromptVersion(data: Partial<PromptVersion>) {
  return api.post<PromptVersion>("/prompt-versions", data);
}
export function activatePromptVersion(id: string) {
  return api.post<PromptVersion>(`/prompt-versions/${id}/activate`);
}
export function listLlmCallRecords(params?: QueryParams) {
  return api.get<PaginatedItems<LlmCallRecord>>(`/llm-call-records${queryString(params)}`);
}
export function createLlmCallRecord(data: Partial<LlmCallRecord>) {
  return api.post<LlmCallRecord>("/llm-call-records", data);
}
export function listFallbackEvents(params?: QueryParams) {
  return api.get<PaginatedItems<FallbackEvent>>(`/fallback-events${queryString(params)}`);
}
export function createFallbackEvent(data: Partial<FallbackEvent>) {
  return api.post<FallbackEvent>("/fallback-events", data);
}
