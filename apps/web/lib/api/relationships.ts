import { api, queryString } from "./client";

export interface RelationshipSignal {
  dimension: string;
  direction: "increase" | "decrease";
}
export interface RelationshipCandidate {
  id: string; status: string; summary: string; dimension_signals: RelationshipSignal[];
  evidence_quotes: Array<{ user?: string; assistant?: string }>;
  evidence_score: number; confidence: number; risk_level: string;
  expected_state_revision: number; created_at: string | null;
}
export interface RelationshipState {
  id: string; revision: number; summary: string; current_revision_id: string | null;
  uncertainty: Record<string, { mean: number; interval_low: number; interval_high: number; effective_evidence: number }>;
  last_evidence_at: string | null;
}
export interface RelationshipRevision { id: string; revision: number; operation: string; reason: string; created_at: string | null }
interface Page<T> { items: T[]; total: number }

export const relationshipApi = {
  state: (companionId: string) => api.get<RelationshipState | null>(`/companions/${companionId}/relationship`),
  candidates: (companionId: string, status?: string) => api.get<Page<RelationshipCandidate>>(`/companions/${companionId}/relationship/candidates${queryString({ status, page_size: 50 })}`),
  revisions: (companionId: string) => api.get<Page<RelationshipRevision>>(`/companions/${companionId}/relationship/revisions${queryString({ page_size: 30 })}`),
  commit: (companionId: string, candidate: RelationshipCandidate) => api.post(`/companions/${companionId}/relationship/candidates/${candidate.id}/commit`, { expected_revision: candidate.expected_state_revision, reason: "用户确认关系理解" }),
  reject: (companionId: string, candidateId: string) => api.post(`/companions/${companionId}/relationship/candidates/${candidateId}/reject`, { reason: "用户拒绝关系理解" }),
  correct: (companionId: string, revisionId: string, expectedRevision: number) => api.post(`/companions/${companionId}/relationship/revisions/${revisionId}/correct`, { expected_revision: expectedRevision, reason: "用户撤回当前关系理解" }),
};
