import { apiGet } from "./client";
import type { RealtimeTraceV5Detail } from "@/lib/types";

function normalizeRealtimeTrace(data: Partial<RealtimeTraceV5Detail> | null): RealtimeTraceV5Detail {
  const item = data ?? {};
  return {
    summary: item.summary ?? {},
    realtime_trace_session: item.realtime_trace_session ?? null,
    events: item.events ?? [],
    participant_event_traces: item.participant_event_traces ?? [],
    speaker_traces: item.speaker_traces ?? [],
    permission_audits: item.permission_audits ?? [],
    memory_gate_traces: item.memory_gate_traces ?? [],
    replay: item.replay ?? null,
    replay_segments: item.replay_segments ?? [],
    redactions: item.redactions ?? [],
    hard_stop_audits: item.hard_stop_audits ?? [],
    trace_steps: item.trace_steps ?? [],
  };
}

export function getRealtimeTrace(traceRunId: string) {
  return apiGet<RealtimeTraceV5Detail>(`/traces/${traceRunId}/realtime`).then(normalizeRealtimeTrace);
}

export function getTraceWithRealtime(traceRunId: string) {
  return apiGet(`/traces/${traceRunId}`);
}
