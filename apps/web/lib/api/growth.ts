import { api } from "./client";

export interface GrowthCandidate {
  id: string; type?: string; status: string;
  conversation_id?: string | null;
  content?: string; summary?: string; reason?: string;
  confidence?: number; evidence_score?: number; risk_level?: string;
  // Extended product fields
  feedback_score?: number;
  impact_preview_json?: Record<string, unknown>;
  profile_patch_preview?: Record<string, unknown>;
  calibration_json?: Record<string, unknown>;
  source_abstraction_candidate_id?: string;
  positive_feedback_count?: number;
  negative_feedback_count?: number;
  evidence_memory_ids?: string[];
  created_at?: string;
}

export interface GrowthRecord {
  id: string; type?: string; status: string;
  content?: string; summary?: string; reason?: string;
  confidence?: number;
  // Extended product fields
  profile_patch_json?: Record<string, unknown>;
  profile_version_before?: Record<string, unknown>;
  profile_version_after?: Record<string, unknown>;
  downstream_trace_run_ids?: string[];
  downstream_memory_ids?: string[];
  downstream_presence_opportunity_ids?: string[];
  revert_impact_json?: Record<string, unknown>;
  feedback_score?: number;
  source_abstraction_candidate_id?: string;
  created_at?: string;
}

export interface GrowthSuggestionPolicy {
  contract_version: "growth-suggestion-policy.v1";
  companion_id: string;
  suggestions_enabled: boolean;
  paused_types: string[];
  updated_at: string | null;
}

export function listGrowthCandidates(params?: Record<string,string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<{ items: GrowthCandidate[]; total: number }>(`/growth-candidates${qs}`);
}
export function commitGrowth(id: string) { return api.post(`/growth-candidates/${id}/commit`); }
export function editGrowthCandidate(id: string, companionId: string, data: { content: string; reason: string }) {
  return api.patch<GrowthCandidate>(`/growth-candidates/${id}?companion_id=${encodeURIComponent(companionId)}`, data);
}
export function rejectGrowth(id: string, data?: Record<string,unknown>) { return api.post(`/growth-candidates/${id}/reject`, data); }
export function listGrowthRecords(params?: Record<string,string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<{ items: GrowthRecord[]; total: number }>(`/growth-records${qs}`);
}
export function getGrowthRecord(id: string) { return api.get<GrowthRecord>(`/growth-records/${id}`); }
export function revertGrowthRecord(id: string, data?: Record<string,unknown>) { return api.post(`/growth-records/${id}/revert`, data); }
export function getGrowthSuggestionPolicy(companionId: string) {
  return api.get<GrowthSuggestionPolicy>(`/companions/${companionId}/growth-policy`);
}
export function saveGrowthSuggestionPolicy(
  companionId: string,
  data: Pick<GrowthSuggestionPolicy, "suggestions_enabled" | "paused_types"> & { expected_updated_at: string | null },
) {
  return api.put<GrowthSuggestionPolicy>(`/companions/${companionId}/growth-policy`, data);
}
