import { apiGet, apiPatch, apiPost, queryString, type QueryParams } from "./client";
import type { PaginatedItems, RealtimeCoPresenceSessionBundle, RealtimeSessionChannel } from "@/lib/types";

function normalizeSession(data: Partial<RealtimeCoPresenceSessionBundle> | null): RealtimeCoPresenceSessionBundle {
  const item = data ?? {};
  return {
    id: item.id ?? "",
    user_id: item.user_id ?? "",
    co_presence_session_id: item.co_presence_session_id ?? null,
    active_companion_id: item.active_companion_id ?? null,
    originating_conversation_id: item.originating_conversation_id ?? null,
    shared_scene_id: item.shared_scene_id ?? null,
    session_title: item.session_title ?? null,
    session_status: item.session_status ?? "created",
    session_source: item.session_source ?? "conversation",
    default_transport: item.default_transport ?? "sse",
    permission_snapshot_json: item.permission_snapshot_json ?? {},
    participant_summary_json: item.participant_summary_json ?? {},
    boundary_snapshot_json: item.boundary_snapshot_json ?? {},
    runtime_state_json: item.runtime_state_json ?? {},
    participants: item.participants ?? [],
    channels: item.channels ?? [],
    recent_state_events: item.recent_state_events ?? [],
    started_at: item.started_at ?? null,
    paused_at: item.paused_at ?? null,
    ended_at: item.ended_at ?? null,
    last_event_at: item.last_event_at ?? null,
    created_at: item.created_at ?? null,
    updated_at: item.updated_at ?? null,
  };
}

function normalizePage(data: PaginatedItems<RealtimeCoPresenceSessionBundle>): PaginatedItems<RealtimeCoPresenceSessionBundle> {
  return { ...data, items: (data.items ?? []).map(normalizeSession) };
}

export function listRealtimeCoPresenceSessions(params?: QueryParams) {
  return apiGet<PaginatedItems<RealtimeCoPresenceSessionBundle>>(
    `/realtime-copresence-sessions${queryString(params)}`,
  ).then(normalizePage);
}

export function createRealtimeCoPresenceSession(data: Record<string, unknown>) {
  return apiPost<RealtimeCoPresenceSessionBundle>("/realtime-copresence-sessions", data).then(normalizeSession);
}

export function getRealtimeCoPresenceSession(sessionId: string) {
  return apiGet<RealtimeCoPresenceSessionBundle>(`/realtime-copresence-sessions/${sessionId}`).then(normalizeSession);
}

export function pauseRealtimeCoPresenceSession(sessionId: string) {
  return apiPost<RealtimeCoPresenceSessionBundle>(`/realtime-copresence-sessions/${sessionId}/pause`).then(normalizeSession);
}

export function resumeRealtimeCoPresenceSession(sessionId: string) {
  return apiPost<RealtimeCoPresenceSessionBundle>(`/realtime-copresence-sessions/${sessionId}/resume`).then(normalizeSession);
}

export function endRealtimeCoPresenceSession(sessionId: string) {
  return apiPost<RealtimeCoPresenceSessionBundle>(`/realtime-copresence-sessions/${sessionId}/end`).then(normalizeSession);
}

export function addRealtimeParticipant(sessionId: string, data: Record<string, unknown>) {
  return apiPost<RealtimeCoPresenceSessionBundle>(`/realtime-copresence-sessions/${sessionId}/participants`, data).then(normalizeSession);
}

export function patchRealtimeParticipant(sessionId: string, participantId: string, data: Record<string, unknown>) {
  return apiPatch<RealtimeCoPresenceSessionBundle>(
    `/realtime-copresence-sessions/${sessionId}/participants/${participantId}`,
    data,
  ).then(normalizeSession);
}

export function listRealtimeSessionChannels(sessionId: string) {
  return apiGet<RealtimeSessionChannel[]>(`/realtime-copresence-sessions/${sessionId}/channels`).then((items) => items ?? []);
}

export function patchRealtimeSessionChannel(sessionId: string, channelId: string, data: Record<string, unknown>) {
  return apiPatch<RealtimeSessionChannel>(`/realtime-copresence-sessions/${sessionId}/channels/${channelId}`, data);
}
