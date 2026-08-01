import { api, queryString } from "./client";

export interface CompanionWorkspaceReadModel {
  companion: { id: string; name: string; subtitle: string | null; current_mode: string; current_status: string | null; current_focus: string | null };
  identity: { display_name: string; identity_summary: string; core_traits: string[]; persona_summary: string; persona_lock_level: string; relationship_role: string; relationship_summary: string };
  boundary: { private_memory_default: string; shared_memory_default: string; cross_companion_read_policy: string; private_to_shared_review_required: boolean; shared_to_private_review_required: boolean; cross_companion_review_required: boolean };
  continuity: { conversation_id: string | null; current_topic: string | null; current_goal: string | null; current_phase: string | null; last_assistant_summary: string | null; suggested_next_steps: unknown[]; updated_at: string | null } | null;
  relationship: Record<string, string | number | null> | null;
  recent_private_memories: Array<{ id: string; type: string; summary: string; updated_at: string | null }>;
  presence_preview: Array<{ id: string; type: string; title: string; message: string | null; priority: number; recommended_surface: string; expires_at: string | null }>;
  review_counts: Record<string, number>;
  governance: { hard_stop_active: boolean; hard_stop_scope: string | null; revoked_channels: number; active_channels: number };
  channels?: Array<{ id: string; status: string; scope: string; outbound_policy: string; memory_review_required: boolean }>;
  channel_presence?: Array<{ status: string; mode: string; muted: boolean; checkin_enabled: boolean; quiet_hours: boolean }>;
  voice?: { profile_status: string | null; profile_name: string | null; session_status: string | null; transcript_retention: string | null; memory_write_policy: string | null; real_audio_enabled: boolean };
}

export interface ChronicleReadModel {
  companion_id: string;
  items: Array<{ id: string; companion_id: string; kind: string; occurred_at: string; title: string; summary: string; source_id: string | null; review_status: string | null; trace_id: string | null }>;
  summaries: Array<{ id: string; version: number; status: string; title: string; summary: string; highlights: string[]; period_start: string; period_end: string; source_event_refs: string[]; invalidation_reason: string | null; created_at: string }>;
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewInboxReadModel {
  companion_id: string;
  items: Array<{ id: string; companion_id: string; kind: string; created_at: string; title: string; summary: string; status: string; risk_level: string | null; source_id: string | null }>;
  counts: Record<string, number>;
  total: number;
  limit: number;
  offset: number;
}

export const companionWorkspaceApi = {
  workspace: (companionId: string) => api.get<CompanionWorkspaceReadModel>(`/companions/${companionId}/workspace`),
  chronicle: (companionId: string, limit = 40, offset = 0) => api.get<ChronicleReadModel>(`/companions/${companionId}/chronicle${queryString({ limit, offset })}`),
  refreshChronicleSummary: (companionId: string, correctionNote?: string) => api.post(`/companions/${companionId}/chronicle/summaries/refresh`, { correction_note: correctionNote || null }),
  invalidateChronicleSummary: (companionId: string, summaryId: string, reason: string) => api.post(`/companions/${companionId}/chronicle/summaries/${summaryId}/invalidate`, { reason }),
  reviewInbox: (companionId: string, limit = 50, offset = 0, kind?: string) => api.get<ReviewInboxReadModel>(`/companions/${companionId}/review-inbox${queryString({ limit, offset, kind })}`),
  reviewInboxPage: async (companionId: string, limit: number, offset: number, kind?: string) => {
    const page = await companionWorkspaceApi.reviewInbox(companionId, limit, offset, kind);
    if (!kind || (page.total === page.counts[kind] && page.items.every((item) => item.kind === kind))) return page;

    const allItems: ReviewInboxReadModel["items"] = [];
    const total = page.counts.total ?? page.total;
    for (let batchOffset = 0; batchOffset < total; batchOffset += 100) {
      const batch = await companionWorkspaceApi.reviewInbox(companionId, 100, batchOffset);
      allItems.push(...batch.items);
    }
    const filtered = allItems.filter((item) => item.kind === kind);
    return { ...page, items: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset };
  },
  decidePersonaGrowth: (companionId: string, candidateId: string, decision: "approved" | "rejected") => api.post(`/companions/${companionId}/persona-growth-candidates/${candidateId}/decision`, { decision }),
};
