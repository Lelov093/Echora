"use client";

import { useCallback, useEffect, useState } from "react";
import {
  activateChannelBinding,
  applyChannelRevoke,
  createChannelPresencePolicy,
  disableChannelBinding,
  enableChannelCheckin,
  listChannelAuditLogs,
  listChannelBindings,
  listChannelBots,
  listChannelDeliveryEvents,
  listChannelHandoffs,
  listChannelMemoryCandidates,
  listChannelMessageEvents,
  listChannelPresencePolicies,
  listChannelProviders,
  listChannelRevokeEvents,
  listChannelTraceEvents,
  listDiscordBotIdentitiesStatus,
  registerChannelBot,
  testDiscordBotConnection,
} from "@/lib/api/channelGateway";
import type {
  ChannelAuditLog,
  ChannelBinding,
  ChannelBotRegistry,
  ChannelContinuityHandoff,
  ChannelDeliveryEvent,
  ChannelMemoryCandidate,
  ChannelMessageEvent,
  ChannelPresencePolicy,
  ChannelProvider,
  ChannelRevokeEvent,
  ChannelTraceEvent,
  DiscordBotIdentityStatus,
  PaginatedItems,
} from "@/lib/types";

interface ChannelGatewayState {
  providers: ChannelProvider[];
  bots: ChannelBotRegistry[];
  bindings: ChannelBinding[];
  discordBots: DiscordBotIdentityStatus[];
  messages: ChannelMessageEvent[];
  deliveries: ChannelDeliveryEvent[];
  candidates: ChannelMemoryCandidate[];
  policies: ChannelPresencePolicy[];
  handoffs: ChannelContinuityHandoff[];
  traces: ChannelTraceEvent[];
  audits: ChannelAuditLog[];
  revokes: ChannelRevokeEvent[];
}

const EMPTY_STATE: ChannelGatewayState = {
  providers: [],
  bots: [],
  bindings: [],
  discordBots: [],
  messages: [],
  deliveries: [],
  candidates: [],
  policies: [],
  handoffs: [],
  traces: [],
  audits: [],
  revokes: [],
};

function items<T>(value: PaginatedItems<T> | null | undefined): T[] {
  return value?.items ?? [];
}

export function useChannelGateway(params?: { userId?: string | null; companionId?: string | null; channelBindingId?: string | null }) {
  const [state, setState] = useState<ChannelGatewayState>(EMPTY_STATE);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const bindingParams = {
      user_id: params?.userId ?? undefined,
      companion_id: params?.companionId ?? undefined,
    };
    const eventParams = {
      channel_binding_id: params?.channelBindingId ?? undefined,
    };
    try {
      const [
        providers,
        bots,
        bindings,
        discordStatus,
        messages,
        deliveries,
        candidates,
        policies,
        handoffs,
        traces,
        audits,
        revokes,
      ] = await Promise.all([
        listChannelProviders({ page_size: 50 }),
        listChannelBots({ page_size: 50 }),
        listChannelBindings({ ...bindingParams, page_size: 50 }),
        listDiscordBotIdentitiesStatus(),
        listChannelMessageEvents({ ...eventParams, page_size: 30 }),
        listChannelDeliveryEvents({ ...eventParams, page_size: 30 }),
        listChannelMemoryCandidates({ ...eventParams, page_size: 30 }),
        listChannelPresencePolicies({ ...eventParams, page_size: 30 }),
        listChannelHandoffs({ ...eventParams, page_size: 30 }),
        listChannelTraceEvents({ ...eventParams, page_size: 30 }),
        listChannelAuditLogs({ ...eventParams, page_size: 30 }),
        listChannelRevokeEvents({ ...eventParams, page_size: 30 }),
      ]);
      setState({
        providers: items(providers),
        bots: items(bots),
        bindings: items(bindings),
        discordBots: discordStatus.bots ?? [],
        messages: items(messages),
        deliveries: items(deliveries),
        candidates: items(candidates),
        policies: items(policies),
        handoffs: items(handoffs),
        traces: items(traces),
        audits: items(audits),
        revokes: items(revokes),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Channel gateway failed to load");
    } finally {
      setLoading(false);
    }
  }, [params?.channelBindingId, params?.companionId, params?.userId]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (!cancelled) void load();
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const run = useCallback(async <T,>(task: () => Promise<T>) => {
    setSaving(true);
    setError(null);
    try {
      const value = await task();
      await load();
      return value;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Channel gateway action failed");
      return null;
    } finally {
      setSaving(false);
    }
  }, [load]);

  return {
    ...state,
    loading,
    saving,
    error,
    reload: load,
    registerBot: (data: Record<string, unknown>) => run(() => registerChannelBot(data)),
    testDiscordBot: (data: Record<string, unknown>) => run(() => testDiscordBotConnection(data)),
    activateBinding: (bindingId: string, data?: Record<string, unknown>) => run(() => activateChannelBinding(bindingId, data)),
    disableBinding: (bindingId: string, data?: Record<string, unknown>) => run(() => disableChannelBinding(bindingId, data)),
    createPresencePolicy: (data: Record<string, unknown>) => run(() => createChannelPresencePolicy(data)),
    enableCheckin: (policyId: string, data: Record<string, unknown>) => run(() => enableChannelCheckin(policyId, data)),
    applyRevoke: (bindingId: string, data?: Record<string, unknown>) => run(() => applyChannelRevoke(bindingId, data)),
  };
}
