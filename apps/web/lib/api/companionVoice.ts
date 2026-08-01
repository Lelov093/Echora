import { apiGet, apiPost, queryString, type QueryParams } from "./client";
import type { CompanionVoiceSessionBundle, PaginatedItems } from "@/lib/types";

function normalizeVoiceSession(data: Partial<CompanionVoiceSessionBundle> | null): CompanionVoiceSessionBundle {
  const item = data ?? {};
  return {
    id: item.id ?? "",
    user_id: item.user_id ?? "",
    realtime_session_id: item.realtime_session_id ?? "",
    co_presence_session_id: item.co_presence_session_id ?? null,
    speaker_companion_id: item.speaker_companion_id ?? "",
    speaker_realtime_participant_id: item.speaker_realtime_participant_id ?? null,
    voice_profile_id: item.voice_profile_id ?? null,
    session_status: item.session_status ?? "created",
    transcript_retention_policy: item.transcript_retention_policy ?? "ephemeral",
    memory_write_policy: item.memory_write_policy ?? "candidate_review",
    allow_multi_speaker: item.allow_multi_speaker ?? false,
    permission_snapshot_json: item.permission_snapshot_json ?? {},
    voice_runtime_json: item.voice_runtime_json ?? {},
    turns: item.turns ?? [],
    stt_events: item.stt_events ?? [],
    tts_events: item.tts_events ?? [],
    turn_taking_events: item.turn_taking_events ?? [],
    interruptions: item.interruptions ?? [],
    persona_guard_runs: item.persona_guard_runs ?? [],
    created_at: item.created_at ?? null,
    updated_at: item.updated_at ?? null,
    metadata: item.metadata ?? {},
  };
}

export function listCompanionVoiceSessions(params?: QueryParams) {
  return apiGet<PaginatedItems<CompanionVoiceSessionBundle>>(
    `/companion-voice-sessions${queryString(params)}`,
  ).then((page) => ({ ...page, items: (page.items ?? []).map(normalizeVoiceSession) }));
}

export function createCompanionVoiceSession(data: Record<string, unknown>) {
  return apiPost<CompanionVoiceSessionBundle>("/companion-voice-sessions", data).then(normalizeVoiceSession);
}

export function getCompanionVoiceSession(voiceSessionId: string) {
  return apiGet<CompanionVoiceSessionBundle>(`/companion-voice-sessions/${voiceSessionId}`).then(normalizeVoiceSession);
}

export function recordSttPartial(voiceSessionId: string, data: Record<string, unknown>) {
  return apiPost(`/companion-voice-sessions/${voiceSessionId}/stt/partial`, data);
}

export function recordSttFinal(voiceSessionId: string, data: Record<string, unknown>) {
  return apiPost(`/companion-voice-sessions/${voiceSessionId}/stt/final`, data);
}

export function recordTtsEvent(voiceSessionId: string, data: Record<string, unknown>) {
  return apiPost(`/companion-voice-sessions/${voiceSessionId}/tts-events`, data);
}

export function decideTurnTaking(voiceSessionId: string, data: Record<string, unknown>) {
  return apiPost(`/companion-voice-sessions/${voiceSessionId}/turn-taking`, data);
}

export function recordVoiceInterruption(voiceSessionId: string, data: Record<string, unknown>) {
  return apiPost(`/companion-voice-sessions/${voiceSessionId}/interruptions`, data);
}

export function runVoicePersonaGuard(voiceSessionId: string, data: Record<string, unknown>) {
  return apiPost(`/companion-voice-sessions/${voiceSessionId}/persona-guard`, data);
}
