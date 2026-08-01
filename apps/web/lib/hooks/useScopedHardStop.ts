"use client";

import { useCallback, useState } from "react";
import {
  stopCompanionScope,
  stopRealtimeChannelScope,
  stopRealtimeSessionScope,
  stopSensorScope,
  triggerScopedHardStop,
} from "@/lib/api/hardStop";
import type { ScopedHardStopResult } from "@/lib/types";

export function useScopedHardStop() {
  const [result, setResult] = useState<ScopedHardStopResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (task: () => Promise<ScopedHardStopResult>) => {
    setSaving(true);
    setError(null);
    try {
      const value = await task();
      setResult(value);
      return value;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scoped hard stop failed");
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  return {
    result,
    saving,
    error,
    trigger: (payload: Record<string, unknown>) => run(() => triggerScopedHardStop(payload)),
    stopSession: (payload: Record<string, unknown>) => run(() => stopRealtimeSessionScope(payload)),
    stopChannel: (payload: Record<string, unknown>) => run(() => stopRealtimeChannelScope(payload)),
    stopCompanion: (payload: Record<string, unknown>) => run(() => stopCompanionScope(payload)),
    stopSensor: (payload: Record<string, unknown>) => run(() => stopSensorScope(payload)),
  };
}
