import { apiGet, apiPost } from "./client";
import type { RealtimeMemoryBufferBundle } from "@/lib/types";

function normalizeBuffer(data: Partial<RealtimeMemoryBufferBundle> | null): RealtimeMemoryBufferBundle {
  const item = data ?? {};
  return {
    id: item.id ?? "",
    user_id: item.user_id ?? "",
    realtime_session_id: item.realtime_session_id ?? null,
    co_presence_session_id: item.co_presence_session_id ?? null,
    shared_scene_id: item.shared_scene_id ?? null,
    owner_companion_id: item.owner_companion_id ?? null,
    buffer_scope: item.buffer_scope ?? "co_presence_session",
    buffer_status: item.buffer_status ?? "active",
    default_memory_action: item.default_memory_action ?? "candidate_review",
    retention_policy: item.retention_policy ?? "ephemeral",
    review_required: item.review_required ?? true,
    auto_write_private_memory: item.auto_write_private_memory ?? false,
    auto_write_shared_memory: item.auto_write_shared_memory ?? false,
    buffer_summary: item.buffer_summary ?? null,
    policy_snapshot_json: item.policy_snapshot_json ?? {},
    items: item.items ?? [],
    companion_private_buffers: item.companion_private_buffers ?? [],
    copresence_buffers: item.copresence_buffers ?? [],
    shared_scene_buffers: item.shared_scene_buffers ?? [],
    created_at: item.created_at ?? null,
    updated_at: item.updated_at ?? null,
    metadata: item.metadata ?? {},
  };
}

export function createRealtimeMemoryBuffer(data: Record<string, unknown>) {
  return apiPost<RealtimeMemoryBufferBundle>("/realtime-memory-buffers", data).then(normalizeBuffer);
}

export function getRealtimeMemoryBuffer(bufferId: string) {
  return apiGet<RealtimeMemoryBufferBundle>(`/realtime-memory-buffers/${bufferId}`).then(normalizeBuffer);
}

export function appendRealtimeMemoryBufferItem(bufferId: string, data: Record<string, unknown>) {
  return apiPost<RealtimeMemoryBufferBundle>(`/realtime-memory-buffers/${bufferId}/items`, data).then(normalizeBuffer);
}

export function expireRealtimeMemoryBufferItems(bufferId: string) {
  return apiPost<RealtimeMemoryBufferBundle>(`/realtime-memory-buffers/${bufferId}/expire-items`).then(normalizeBuffer);
}

export function writeRealtimeMemoryGateTrace(bufferId: string, data: Record<string, unknown>) {
  return apiPost(`/realtime-memory-buffers/${bufferId}/memory-gate-trace`, data);
}

export function detectRealtimeSalientMoment(bufferItemId: string, data: Record<string, unknown>) {
  return apiPost(`/realtime-memory-buffer-items/${bufferItemId}/salient-moment`, data);
}

export function getRealtimeSalientMoment(momentId: string) {
  return apiGet(`/realtime-salient-moments/${momentId}`);
}

export function createRealtimeSharedMemoryCandidate(momentId: string, data: Record<string, unknown>) {
  return apiPost(`/realtime-salient-moments/${momentId}/shared-memory-candidate`, data);
}

export function decideRealtimeSharedMemoryCandidate(candidateId: string, decision: "approved" | "rejected") {
  return apiPost(`/realtime-shared-memory-candidates/${candidateId}/decision`, { decision });
}
