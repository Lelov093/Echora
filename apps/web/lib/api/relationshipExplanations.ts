import { api } from "./client";

// Detail-level API client.
// Reserved for future relationship detail drawers.
// Do not remove: contract is validated by backend smoke tests.

export interface RelationshipExplanation {
  id: string;
  dimension: string;
  title?: string | null;
  explanation: string;
  previous_value?: number | null;
  new_value?: number | null;
  delta?: number | null;
  confidence: number;
  evidence_memory_ids?: string[];
  user_visible: boolean;
  created_at?: string | null;
}

export function getRelationshipExplanation(explanationId: string) {
  return api.get<RelationshipExplanation>(`/relationship-explanations/${explanationId}`);
}

export function listRelationshipExplanations(companionId?: string) {
  const params: Record<string, string> = {};
  if (companionId) params.companion_id = companionId;
  const qs = Object.keys(params).length ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<{ items: RelationshipExplanation[]; total: number }>(`/relationship-explanations${qs}`);
}

export function getCompanionRelationshipExplanations(companionId: string) {
  return api.get<{ items: RelationshipExplanation[] }>(`/companions/${companionId}/relationship/explanations`);
}
