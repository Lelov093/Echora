import { apiDelete, apiGet, apiPatch, apiPost, queryString, type QueryParams } from "./client";
import type {
  ChannelAuditLog,
  ChannelBinding,
  DiscordDmBinding,
  DiscordDmDelivery,
  ChannelBotRegistry,
  ChannelContinuityHandoff,
  ChannelDeliveryEvent,
  ChannelMemoryCandidate,
  ChannelMemoryReview,
  ChannelMessageEvent,
  ChannelPresencePolicy,
  ChannelProvider,
  ChannelRevokeEvent,
  ChannelTraceEvent,
  DiscordBotIdentityStatus,
  PaginatedItems,
} from "@/lib/types";

export function listChannelProviders(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelProvider>>(`/channel-providers${queryString(params)}`);
}

export function getChannelProviderByKey(providerKey: string) {
  return apiGet<ChannelProvider>(`/channel-providers/by-key/${providerKey}`);
}

export function listChannelBots(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelBotRegistry>>(`/channel-bots${queryString(params)}`);
}

export function registerChannelBot(data: Record<string, unknown>) {
  return apiPost<ChannelBotRegistry>("/channel-bots", data);
}

export function listChannelBindings(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelBinding>>(`/channel-bindings${queryString(params)}`);
}

export function createChannelBinding(data: Record<string, unknown>) {
  return apiPost<ChannelBinding>("/channel-bindings", data);
}

export function getChannelBinding(bindingId: string) {
  return apiGet<ChannelBinding>(`/channel-bindings/${bindingId}`);
}

export function activateChannelBinding(bindingId: string, data?: Record<string, unknown>) {
  return apiPost<ChannelBinding>(`/channel-bindings/${bindingId}/activate`, data ?? {});
}

export function disableChannelBinding(bindingId: string, data?: Record<string, unknown>) {
  return apiPost<ChannelBinding>(`/channel-bindings/${bindingId}/disable`, data ?? {});
}

export function revokeChannelBinding(bindingId: string, data?: Record<string, unknown>) {
  return apiPost<ChannelBinding>(`/channel-bindings/${bindingId}/revoke`, data ?? {});
}

export function listDiscordBotIdentitiesStatus() {
  return apiGet<{ registry_configured: boolean; registry_status: string; bots: DiscordBotIdentityStatus[] }>(
    "/discord-bot-identities/status",
  );
}

export interface DiscordIdentityBinding {
  bot_key: string;
  display_name?: string;
  binding_status: string;
  binding?: { companion_id?: string | null; companion_name?: string | null; status?: string | null; revision?: number | null } | null;
}

export function listDiscordBotIdentityBindings() {
  return apiGet<{ bots: DiscordIdentityBinding[] }>("/discord-bot-identities/bindings");
}

export function bindDiscordBotToCompanion(data: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>("/discord-bot-identities/bind-companion", data);
}

export type DiscordRebindPreflight = {
  allowed: boolean;
  requires_explicit_pause?: boolean;
  current_identity?: { id: string; companion_id: string; revision: number; status: string } | null;
  dependencies?: {
    live_dm_binding_count?: number;
    pending_delivery_count?: number;
    live_room_binding_count?: number;
  };
};

export function preflightDiscordBotRebind(data: { bot_key: string; companion_id: string }) {
  return apiPost<DiscordRebindPreflight>("/discord-bot-identities/rebind-preflight", data);
}

export function unbindDiscordBot(botIdentityId: string) {
  return apiDelete<Record<string, unknown>>(`/discord-bot-identities/${botIdentityId}/binding`);
}

export function testDiscordBotConnection(data: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>("/discord-bot-identities/test-connection", data);
}

export function listDiscordDmBindings(params?: QueryParams) {
  return apiGet<{ items: DiscordDmBinding[] }>(`/discord-bot-identities/dm-bindings${queryString(params)}`);
}

export function listDiscordDmDeliveries(params?: QueryParams) {
  return apiGet<{ items: DiscordDmDelivery[] }>(`/discord-bot-identities/dm-deliveries${queryString(params)}`);
}

export function transitionDiscordDmBinding(
  bindingId: string,
  action: "pause" | "resume" | "revoke" | "switch" | "new",
  data: { expected_revision: number; conversation_id?: string },
) {
  return apiPost<DiscordDmBinding>(`/discord-bot-identities/dm-bindings/${bindingId}/${action}`, data);
}

export function listChannelMessageEvents(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelMessageEvent>>(`/channel-message-events${queryString(params)}`);
}

export function ingestChannelInbound(data: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>("/channel-message-events/inbound", data);
}

export function listChannelDeliveryEvents(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelDeliveryEvent>>(`/channel-delivery-events${queryString(params)}`);
}

export function queueChannelOutbound(data: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>("/channel-delivery-events/outbound", data);
}

export function listChannelMemoryCandidates(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelMemoryCandidate>>(`/channel-memory-candidates${queryString(params)}`);
}

export function createChannelMemoryCandidate(data: Record<string, unknown>) {
  return apiPost<ChannelMemoryCandidate>("/channel-memory-candidates", data);
}

export function approveChannelMemoryCandidate(candidateId: string, data?: Record<string, unknown>) {
  return apiPost<ChannelMemoryCandidate>(`/channel-memory-candidates/${candidateId}/approve`, data ?? {});
}

export function rejectChannelMemoryCandidate(candidateId: string, data?: Record<string, unknown>) {
  return apiPost<ChannelMemoryCandidate>(`/channel-memory-candidates/${candidateId}/reject`, data ?? {});
}

export function redactChannelMemoryCandidate(candidateId: string, data?: Record<string, unknown>) {
  return apiPost<ChannelMemoryCandidate>(`/channel-memory-candidates/${candidateId}/redact`, data ?? {});
}

export function listChannelMemoryReviews(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelMemoryReview>>(`/channel-memory-reviews${queryString(params)}`);
}

export function listChannelPresencePolicies(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelPresencePolicy>>(`/channel-presence-policies${queryString(params)}`);
}

export function createChannelPresencePolicy(data: Record<string, unknown>) {
  return apiPost<ChannelPresencePolicy>("/channel-presence-policies", data);
}

export function updateChannelPresencePolicy(policyId: string, data: Record<string, unknown>) {
  return apiPatch<ChannelPresencePolicy>(`/channel-presence-policies/${policyId}`, data);
}

export function enableChannelCheckin(policyId: string, data: Record<string, unknown>) {
  return apiPost<ChannelPresencePolicy>(`/channel-presence-policies/${policyId}/enable-checkin`, data);
}

export function evaluateChannelCheckin(data: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>("/channel-checkins/evaluate", data);
}

export function listChannelHandoffs(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelContinuityHandoff>>(`/channel-continuity/handoffs${queryString(params)}`);
}

export function createWebToChannelHandoff(data: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>("/channel-continuity/web-to-channel", data);
}

export function createChannelToWebHandoff(data: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>("/channel-continuity/channel-to-web", data);
}

export function listChannelTraceEvents(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelTraceEvent>>(`/channel-trace-events${queryString(params)}`);
}

export function listChannelAuditLogs(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelAuditLog>>(`/channel-audit-logs${queryString(params)}`);
}

export function listChannelRevokeEvents(params?: QueryParams) {
  return apiGet<PaginatedItems<ChannelRevokeEvent>>(`/channel-revoke-events${queryString(params)}`);
}

export function applyChannelRevoke(bindingId: string, data?: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>(`/channel-revokes/${bindingId}/apply`, data ?? {});
}
