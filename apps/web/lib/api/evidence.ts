import { api, queryString, type QueryParams } from "./client";
import type { EvidenceSufficiencyEvent, PaginatedItems } from "@/lib/types";

export interface GrowthConsistencyCheck {
  id: string;
  growth_candidate_id?: string | null;
  trace_run_id?: string | null;
  consistency_score: number;
  risk_level: string;
  status: string;
  recommendation?: string | null;
  conflict_json?: Record<string, unknown>;
  duplication_json?: Record<string, unknown>;
}

export interface OutdatedMemoryFlag {
  id: string;
  memory_id: string;
  trace_run_id?: string | null;
  reason: string;
  confidence: number;
  status: string;
  suggested_action: string;
  evidence_refs?: Record<string, unknown>[];
}

export interface OutdatedMemoryReview {
  id: string;
  outdated_memory_flag_id: string;
  memory_id: string;
  decision: string;
  edited_content?: string | null;
  reason?: string | null;
}

export function listEvidenceSufficiencyEvents(params?: QueryParams) {
  return api.get<PaginatedItems<EvidenceSufficiencyEvent>>(`/evidence-sufficiency-events${queryString(params)}`);
}
export function createEvidenceSufficiencyEvent(data: Partial<EvidenceSufficiencyEvent>) {
  return api.post<EvidenceSufficiencyEvent>("/evidence-sufficiency-events", data);
}
export function listGrowthConsistencyChecks(params?: QueryParams) {
  return api.get<PaginatedItems<GrowthConsistencyCheck>>(`/growth-consistency-checks${queryString(params)}`);
}
export function createGrowthConsistencyCheck(data: Partial<GrowthConsistencyCheck>) {
  return api.post<GrowthConsistencyCheck>("/growth-consistency-checks", data);
}
export function listOutdatedMemoryFlags(params?: QueryParams) {
  return api.get<PaginatedItems<OutdatedMemoryFlag>>(`/outdated-memory-flags${queryString(params)}`);
}
export function createOutdatedMemoryFlag(data: Partial<OutdatedMemoryFlag>) {
  return api.post<OutdatedMemoryFlag>("/outdated-memory-flags", data);
}
export function updateOutdatedMemoryFlag(id: string, data: Partial<OutdatedMemoryFlag>) {
  return api.patch<OutdatedMemoryFlag>(`/outdated-memory-flags/${id}`, data);
}
export function listOutdatedMemoryReviews(params?: QueryParams) {
  return api.get<PaginatedItems<OutdatedMemoryReview>>(`/outdated-memory-reviews${queryString(params)}`);
}
export function createOutdatedMemoryReview(flagId: string, data: Partial<OutdatedMemoryReview>) {
  return api.post<OutdatedMemoryReview>(`/outdated-memory-flags/${flagId}/review`, data);
}
