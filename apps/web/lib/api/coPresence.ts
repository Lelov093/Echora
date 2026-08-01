import { apiGet, apiPatch, apiPost } from "./client";
import type {
  CompanionRoomBundle,
  CompanionRoomMessage,
  CompanionRoomTurn,
  CoPresenceSessionBundle,
  DiscordChannelIngressProjection,
  DiscordChannelProjection,
  DiscordGuildProjection,
  DiscordRoomBindingProjection,
  DiscordRoomBotIdentity,
  PaginatedItems,
} from "@/lib/types";

function toQuery(params?: Record<string, string | number | undefined | null>) {
  if (!params) return "";
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "");
  return entries.length > 0 ? `?${new URLSearchParams(entries.map(([key, value]) => [key, String(value)])).toString()}` : "";
}

export function listCoPresenceSessions(params?: Record<string, string | number | undefined | null>) {
  return apiGet<PaginatedItems<CoPresenceSessionBundle>>(`/co-presence-sessions${toQuery(params)}`);
}

export function createCoPresenceSession(data: Record<string, unknown>) {
  return apiPost<CoPresenceSessionBundle>("/co-presence-sessions", data);
}

export function getCoPresenceSession(sessionId: string) {
  return apiGet<CoPresenceSessionBundle>(`/co-presence-sessions/${sessionId}`);
}

export function getCompanionRoom(sessionId: string) {
  return apiGet<CompanionRoomBundle>(`/companion-rooms/${sessionId}`);
}

export function patchCoPresenceSession(sessionId: string, data: Record<string, unknown>) {
  return apiPatch<CoPresenceSessionBundle>(`/co-presence-sessions/${sessionId}`, data);
}

export function addCoPresenceParticipant(sessionId: string, data: Record<string, unknown>) {
  return apiPost<CoPresenceSessionBundle>(`/co-presence-sessions/${sessionId}/participants`, data);
}

export function patchCoPresenceParticipant(sessionId: string, participantId: string, data: Record<string, unknown>) {
  return apiPatch<CoPresenceSessionBundle>(`/co-presence-sessions/${sessionId}/participants/${participantId}`, data);
}

export function endCoPresenceSession(sessionId: string) {
  return apiPost<CoPresenceSessionBundle>(`/co-presence-sessions/${sessionId}/end`);
}

export type CompanionRoomCreateInput = {
  primary_companion_id: string;
  title: string;
  summary?: string;
  participants: Array<{ companion_id: string; role: "active_companion" | "observing_companion" }>;
};

export function createCompanionRoom(data: CompanionRoomCreateInput) {
  return apiPost<{ session: CompanionRoomBundle; scene: { id: string }; conversation: { id: string } }>("/companion-rooms", data);
}

export function updateCompanionRoom(sessionId: string, data: { title?: string; summary?: string }) {
  return apiPatch<{ session: CoPresenceSessionBundle; shared_scene_ids: string[] }>(`/companion-rooms/${sessionId}`, data);
}

export function archiveCompanionRoom(sessionId: string) {
  return apiPost<{ session: CompanionRoomBundle; scene_close_failures: string[] }>(`/companion-rooms/${sessionId}/archive`);
}

export function restoreCompanionRoom(sessionId: string, expectedRosterRevision: number, reason?: string) {
  return apiPost<CompanionRoomBundle>(`/companion-rooms/${sessionId}/restore`, {
    expected_roster_revision: expectedRosterRevision,
    reason,
  });
}

export function inviteCompanionRoomMember(sessionId: string, data: {
  companion_id: string;
  mode: "speaker" | "observer";
  expected_roster_revision: number;
  reason?: string;
}) {
  return apiPost<CompanionRoomBundle>(`/companion-rooms/${sessionId}/members`, data);
}

export function transitionCompanionRoomMember(sessionId: string, participantId: string, data: {
  action: "speaker" | "observer" | "mute" | "inactivate" | "reactivate" | "revoke";
  expected_roster_revision: number;
  expected_participant_revision: number;
  reason?: string;
}) {
  return apiPost<CompanionRoomBundle>(`/companion-rooms/${sessionId}/members/${participantId}/transition`, data);
}

export function listCompanionRoomMessages(sessionId: string, limit = 100) {
  return apiGet<{ items: CompanionRoomMessage[]; total: number; room_id: string; conversation_id: string }>(
    `/companion-rooms/${sessionId}/messages?limit=${limit}`,
  );
}

export function runCompanionRoomTurn(sessionId: string, data: {
  content: string;
  target_companion_ids?: string[];
  idempotency_key?: string;
}) {
  return apiPost<CompanionRoomTurn>(`/companion-rooms/${sessionId}/turns`, data);
}

export function createCompanionRoomSuccessor(sessionId: string, data: {
  title: string;
  summary?: string;
  continuation_summary: string;
  confirm_reviewed: true;
  expected_roster_revision: number;
}) {
  return apiPost<{ session: CompanionRoomBundle; continuation_capsule: Record<string, unknown> }>(
    `/companion-rooms/${sessionId}/successor`, data,
  );
}

export function cancelCompanionRoomTurn(sessionId: string, turnId: string) {
  return apiPost<CompanionRoomTurn>(`/companion-rooms/${sessionId}/turns/${turnId}/cancel`);
}

export function retryCompanionRoomTurnStep(sessionId: string, turnId: string, stepId: string) {
  return apiPost<CompanionRoomTurn>(`/companion-rooms/${sessionId}/turns/${turnId}/steps/${stepId}/retry`);
}

export function listDiscordRoomGuilds(userId?: string) {
  return apiGet<{ items: DiscordGuildProjection[] }>(`/companion-room-channels/guilds${toQuery({ user_id: userId })}`);
}

export function createDiscordRoomGuild(data: { user_id: string; provider_guild_ref: string; guild_display_name: string }) {
  return apiPost<DiscordGuildProjection>("/companion-room-channels/guilds", data);
}

export function listDiscordRoomChannels(params?: { guild_id?: string; user_id?: string }) {
  return apiGet<{ items: DiscordChannelProjection[] }>(`/companion-room-channels/channels${toQuery(params)}`);
}

export function createDiscordRoomChannel(guildId: string, data: {
  provider_channel_ref: string;
  channel_display_name: string;
  permission_status: "unverified" | "ready" | "blocked";
}) {
  return apiPost<DiscordChannelProjection>(`/companion-room-channels/guilds/${guildId}/channels`, data);
}

export function listDiscordRoomBotIdentities(userId?: string) {
  return apiGet<{ items: DiscordRoomBotIdentity[] }>(`/companion-room-channels/bot-identities${toQuery({ user_id: userId })}`);
}

export function bindDiscordChannelToRoom(channelId: string, data: {
  room_id: string;
  provider_bot_ids: string[];
  expected_channel_revision: number;
  expected_room_roster_revision: number;
  mention_policy: "mention_only" | "coordinator_managed" | "observe_only";
}) {
  return apiPost<DiscordRoomBindingProjection>(`/companion-room-channels/channels/${channelId}/bind`, data);
}

export function transitionDiscordRoomBinding(bindingId: string, action: "pause" | "resume" | "revoke", data: { expected_revision: number; reason?: string }) {
  return apiPost<DiscordRoomBindingProjection>(`/companion-room-channels/bindings/${bindingId}/${action}`, data);
}

export function listDiscordRoomIngresses(roomId: string, limit = 30) {
  return apiGet<{ items: DiscordChannelIngressProjection[] }>(`/companion-room-channels/rooms/${roomId}/ingresses?limit=${limit}`);
}
