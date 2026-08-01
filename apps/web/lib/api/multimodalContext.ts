import { apiGet, apiPost } from "./client";
import type { MultimodalContextEventBundle } from "@/lib/types";

function normalizeContext(data: Partial<MultimodalContextEventBundle> | null): MultimodalContextEventBundle {
  const item = data ?? {};
  return {
    id: item.id ?? "",
    user_id: item.user_id ?? "",
    realtime_session_id: item.realtime_session_id ?? null,
    co_presence_session_id: item.co_presence_session_id ?? null,
    shared_scene_id: item.shared_scene_id ?? null,
    source_participant_id: item.source_participant_id ?? null,
    context_type: item.context_type ?? "image",
    context_source: item.context_source ?? "manual",
    context_status: item.context_status ?? "created",
    raw_data_ref: item.raw_data_ref ?? null,
    raw_data_retention_policy: item.raw_data_retention_policy ?? "ephemeral",
    raw_data_storage_allowed: item.raw_data_storage_allowed ?? false,
    retention_policy_json: item.retention_policy_json ?? {},
    permission_snapshot_json: item.permission_snapshot_json ?? {},
    visibility_summary_json: item.visibility_summary_json ?? {},
    redaction_status: item.redaction_status ?? "pending",
    expires_at: item.expires_at ?? null,
    permissions: item.permissions ?? [],
    retention: item.retention ?? null,
    created_at: item.created_at ?? null,
    updated_at: item.updated_at ?? null,
    metadata: item.metadata ?? {},
  };
}

export function createMultimodalContextEvent(data: Record<string, unknown>) {
  return apiPost<MultimodalContextEventBundle>("/realtime-multimodal-context-events", data).then(normalizeContext);
}

export function getMultimodalContextEvent(contextEventId: string) {
  return apiGet<MultimodalContextEventBundle>(`/realtime-multimodal-context-events/${contextEventId}`).then(normalizeContext);
}

export function recordContextPermission(contextEventId: string, data: Record<string, unknown>) {
  return apiPost(`/realtime-multimodal-context-events/${contextEventId}/permissions`, data);
}

export function checkParticipantContextVisibility(contextEventId: string, participantId: string) {
  return apiGet(`/realtime-multimodal-context-events/${contextEventId}/participants/${participantId}/visibility`);
}

export function checkContextRetention(contextEventId: string) {
  return apiGet(`/realtime-multimodal-context-events/${contextEventId}/retention`);
}

export function expireEphemeralContext(contextEventId: string) {
  return apiPost(`/realtime-multimodal-context-events/${contextEventId}/expire`);
}
