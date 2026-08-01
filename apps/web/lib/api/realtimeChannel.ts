import { API_BASE, apiGet, apiPost, queryString } from "./client";
import type { JsonObject, RealtimeChannelEvent } from "@/lib/types";

export interface RealtimeChannelSseOptions {
  channelId: string;
  maxEvents?: number;
  lastEventId?: string | null;
  reconnect?: boolean;
  reconnectDelayMs?: number;
  onEvent?: (event: RealtimeChannelEvent, raw: MessageEvent<string>) => void;
  onOpen?: () => void;
  onError?: (event: Event) => void;
}

export interface RealtimeChannelSseConnection {
  connect: () => void;
  reconnect: () => void;
  close: () => void;
  getLastEventId: () => string | null;
}

function normalizeEvent(data: Partial<RealtimeChannelEvent> | null): RealtimeChannelEvent {
  const item = data ?? {};
  return {
    id: item.id ?? "",
    realtime_session_id: item.realtime_session_id ?? null,
    channel_id: item.channel_id ?? null,
    event: item.event ?? item.event_type ?? "event.published",
    event_type: item.event_type ?? item.event,
    event_status: item.event_status ?? "recorded",
    payload: item.payload ?? {},
    preview: item.preview ?? null,
    occurred_at: item.occurred_at ?? null,
  };
}

export function publishRealtimeChannelEvent(channelId: string, data: { event_type: string; payload?: JsonObject; preview?: string | null }) {
  return apiPost<RealtimeChannelEvent>(`/realtime-channels/${channelId}/events`, data).then(normalizeEvent);
}

export function listRecentRealtimeChannelEvents(channelId: string, params?: { last_event_id?: string | null; limit?: number }) {
  return apiGet<RealtimeChannelEvent[]>(
    `/realtime-channels/${channelId}/events/recent${queryString(params)}`,
  ).then((items) => (items ?? []).map(normalizeEvent));
}

export function createRealtimeChannelSseConnection(options: RealtimeChannelSseOptions): RealtimeChannelSseConnection {
  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let lastEventId = options.lastEventId ?? null;

  const close = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    source?.close();
    source = null;
  };

  const connect = () => {
    close();
    const path = `/realtime-channels/${options.channelId}/events${queryString({
      last_event_id: lastEventId,
      max_events: options.maxEvents ?? 50,
    })}`;
    source = new EventSource(`${API_BASE}${path}`);
    source.onopen = () => options.onOpen?.();
    source.onerror = (event) => {
      options.onError?.(event);
      if (options.reconnect !== false && !reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          connect();
        }, options.reconnectDelayMs ?? 2500);
      }
    };
    source.onmessage = (event) => {
      if (event.lastEventId) lastEventId = event.lastEventId;
      try {
        options.onEvent?.(normalizeEvent(JSON.parse(event.data) as RealtimeChannelEvent), event);
      } catch {
        options.onEvent?.(normalizeEvent({ id: event.lastEventId, event: event.type, payload: { raw: event.data } }), event);
      }
    };
    for (const eventType of ["session.started", "transcript.partial", "response.delta", "permission.changed", "hard_stop.triggered"]) {
      source.addEventListener(eventType, (event) => {
        const message = event as MessageEvent<string>;
        if (message.lastEventId) lastEventId = message.lastEventId;
        try {
          options.onEvent?.(normalizeEvent(JSON.parse(message.data) as RealtimeChannelEvent), message);
        } catch {
          options.onEvent?.(normalizeEvent({ id: message.lastEventId, event: eventType, payload: { raw: message.data } }), message);
        }
      });
    }
  };

  return {
    connect,
    reconnect: connect,
    close,
    getLastEventId: () => lastEventId,
  };
}
