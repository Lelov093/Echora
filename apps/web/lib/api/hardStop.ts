import { apiPost } from "./client";
import type { ScopedHardStopResult } from "@/lib/types";

function normalizeHardStop(data: Partial<ScopedHardStopResult> | null): ScopedHardStopResult {
  return {
    hard_stop: data?.hard_stop ?? {},
    audit: data?.audit ?? {},
  };
}

export function triggerScopedHardStop(data: Record<string, unknown>) {
  return apiPost<ScopedHardStopResult>("/hard-stops", data).then(normalizeHardStop);
}

export function stopRealtimeSessionScope(data: Record<string, unknown>) {
  return apiPost<ScopedHardStopResult>("/hard-stops/session", data).then(normalizeHardStop);
}

export function stopRealtimeChannelScope(data: Record<string, unknown>) {
  return apiPost<ScopedHardStopResult>("/hard-stops/channel", data).then(normalizeHardStop);
}

export function stopCompanionScope(data: Record<string, unknown>) {
  return apiPost<ScopedHardStopResult>("/hard-stops/companion", data).then(normalizeHardStop);
}

export function stopSensorScope(data: Record<string, unknown>) {
  return apiPost<ScopedHardStopResult>("/hard-stops/sensor", data).then(normalizeHardStop);
}
