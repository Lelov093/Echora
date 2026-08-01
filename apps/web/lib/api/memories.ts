import { api } from "./client";

export interface MemoryItem {
  id: string; companion_id: string; type: string; state: string;
  content: string; summary?: string; memory_strength: number; confidence: number;
  content_revision: number; content_hash?: string | null;
  reactivation_count?: number; last_reactivated_at?: string; created_at: string; updated_at: string;
}

export interface MemoryCandidate {
  id: string; companion_id: string; content: string; suggested_type?: string; suggested_state?: string;
  status: string; score: number; confidence?: number; reason?: string;
  source_conversation_id?: string; source_run_id?: string; created_at: string; updated_at: string;
}

export function listMemories(params?: Record<string,string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get(`/memories${qs}`);
}
const scope = (companionId: string) => `companion_id=${encodeURIComponent(companionId)}`;
export function createMemory(data: { user_id: string; companion_id: string; content: string; summary?: string; type?: string; importance?: number; confidence?: number }) { return api.post<MemoryItem>("/memories", data); }
export function getMemory(id: string, companionId: string) { return api.get<MemoryItem>(`/memories/${id}?${scope(companionId)}`); }
export interface MemoryRevision { id: string; memory_id: string; companion_id: string; revision: number; content: string; summary?: string | null; operation: "created" | "corrected" | "merged" | "restored"; reason: string; restored_from_revision_id?: string | null; embedding_provider?: string | null; embedding_model?: string | null; created_at: string; }
export function correctMemory(id: string, companionId: string, data: { content: string; summary?: string; reason: string; expected_revision: number }) { return api.patch<MemoryItem>(`/memories/${id}?${scope(companionId)}`, data); }
export function listMemoryRevisions(id: string, companionId: string) { return api.get<{ items: MemoryRevision[]; total: number; memory: MemoryItem }>(`/memories/${id}/revisions?${scope(companionId)}`); }
export function restoreMemoryRevision(id: string, revisionId: string, companionId: string, data: { expected_revision: number; reason: string }) { return api.post<MemoryItem>(`/memories/${id}/revisions/${revisionId}/restore?${scope(companionId)}`, data); }
export function lockMemory(id: string, companionId: string) { return api.post(`/memories/${id}/lock?${scope(companionId)}`); }
export function fadeMemory(id: string, companionId: string, data?: Record<string,unknown>) { return api.post(`/memories/${id}/fade?${scope(companionId)}`, data); }
export function archiveMemory(id: string, companionId: string) { return api.post(`/memories/${id}/archive?${scope(companionId)}`); }
export function reactivateMemory(id: string, companionId: string) { return api.post(`/memories/${id}/reactivate?${scope(companionId)}`); }
export function deleteMemory(id: string, companionId: string) { return api.delete(`/memories/${id}?${scope(companionId)}`); }

export function listMemoryCandidates(params?: Record<string,string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<{ items: MemoryCandidate[] }>(`/memory-candidates${qs}`);
}
export function acceptCandidate(id: string) { return api.post(`/memory-candidates/${id}/accept`); }
export function commitCandidate(id: string) { return api.post(`/memory-candidates/${id}/commit`); }
export function editCandidate(id: string, data: { content: string; summary?: string; type?: string; accept_after_edit?: boolean }) { return api.post(`/memory-candidates/${id}/edit`, data); }
export function rejectCandidate(id: string, data?: Record<string,unknown>) { return api.post(`/memory-candidates/${id}/reject`, data); }

export interface ContextDocument { id: string; companion_id: string; conversation_id?: string | null; document_kind: "recent_summary" | "long_term_profile"; version: number; status: "active" | "superseded" | "invalidated"; content: string; structured: Record<string, unknown>; source_message_ids: string[]; source_memory_ids: string[]; confidence: number; generation_reason: string; generated_by_provider?: string | null; generated_by_model?: string | null; user_corrected: boolean; created_at: string; updated_at: string; }
export function listContextDocuments(companionId: string, includeHistory = false) { return api.get<{ items: ContextDocument[]; total: number }>(`/companions/${companionId}/context-documents?include_history=${includeHistory}`); }
export function refreshContextDocuments(companionId: string, data: { user_id: string; conversation_id: string; force?: boolean; reason?: string }) { return api.post<{ outcome: string; reason: string; documents: ContextDocument[] }>(`/companions/${companionId}/context-documents/refresh`, data); }
export function correctContextDocument(companionId: string, id: string, data: { expected_version: number; content: string; reason: string }) { return api.patch<ContextDocument>(`/companions/${companionId}/context-documents/${id}`, data); }
export function restoreContextDocument(companionId: string, id: string, data: { expected_version: number; reason: string }) { return api.post<ContextDocument>(`/companions/${companionId}/context-documents/${id}/restore`, data); }
export function invalidateContextDocument(companionId: string, id: string, data: { expected_version: number; reason: string }) { return api.post<ContextDocument>(`/companions/${companionId}/context-documents/${id}/invalidate`, data); }
