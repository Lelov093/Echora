"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createRealtimeChannelSseConnection,
  listRecentRealtimeChannelEvents,
  publishRealtimeChannelEvent,
  type RealtimeChannelSseConnection,
} from "@/lib/api/realtimeChannel";
import type { JsonObject, RealtimeChannelEvent } from "@/lib/types";

export function useRealtimeChannel(channelId: string | null, options: { autoConnect?: boolean; maxEvents?: number } = {}) {
  const [events, setEvents] = useState<RealtimeChannelEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(Boolean(channelId));
  const [error, setError] = useState<string | null>(null);
  const connectionRef = useRef<RealtimeChannelSseConnection | null>(null);

  const loadRecent = useCallback(async () => {
    if (!channelId) {
      setEvents([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setEvents(await listRecentRealtimeChannelEvents(channelId, { limit: options.maxEvents ?? 50 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load realtime channel events");
    } finally {
      setLoading(false);
    }
  }, [channelId, options.maxEvents]);

  const close = useCallback(() => {
    connectionRef.current?.close();
    connectionRef.current = null;
    setConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!channelId) return;
    close();
    const connection = createRealtimeChannelSseConnection({
      channelId,
      maxEvents: options.maxEvents,
      onOpen: () => setConnected(true),
      onError: () => setError("Realtime event stream disconnected"),
      onEvent: (event) => {
        setEvents((current) => {
          if (current.some((item) => item.id === event.id)) return current;
          return [event, ...current].slice(0, options.maxEvents ?? 50);
        });
      },
    });
    connectionRef.current = connection;
    connection.connect();
  }, [channelId, close, options.maxEvents]);

  const publish = useCallback(
    (eventType: string, payload: JsonObject = {}, preview?: string | null) => {
      if (!channelId) return Promise.resolve(null);
      return publishRealtimeChannelEvent(channelId, { event_type: eventType, payload, preview });
    },
    [channelId],
  );

  /* eslint-disable react-hooks/set-state-in-effect -- async API load state intentionally updated after mount */
  useEffect(() => {
    loadRecent();
  }, [loadRecent]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (!options.autoConnect) return () => close();
    const timer = setTimeout(() => connect(), 0);
    return () => {
      clearTimeout(timer);
      close();
    };
  }, [connect, close, options.autoConnect]);

  return { events, loading, error, connected, reload: loadRecent, connect, close, publish };
}
