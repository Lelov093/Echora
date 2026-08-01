import { api } from "./client";

export interface TimelineEvent {
  id: string;
  memory_id: string;
  event_type: string;
  summary?: string | null;
  details?: Record<string, unknown>;
  created_at?: string | null;
}

export interface UsageEvent {
  id: string;
  memory_id?: string | null;
  trace_run_id?: string | null;
  event_type: string;
  summary?: string | null;
  details?: Record<string, unknown>;
  created_at?: string | null;
}

export interface LifecycleEvent {
  id: string;
  memory_id?: string | null;
  event_type: string;
  from_state?: string | null;
  to_state?: string | null;
  reason?: string | null;
  details?: Record<string, unknown>;
  created_at?: string | null;
}

export interface TimelineResponse {
  items: TimelineEvent[];
  total: number;
}

export interface UsageEventsResponse {
  items: UsageEvent[];
  total: number;
}

export interface LifecycleEventsResponse {
  items: LifecycleEvent[];
  total: number;
}

export function getMemoryTimeline(companionId: string, page?: number) {
  const params: Record<string, string> = { companion_id: companionId };
  if (page != null) params.page = String(page);
  const qs = "?" + new URLSearchParams(params).toString();
  return api.get<TimelineResponse>(`/memories/timeline${qs}`);
}

export function getMemoryTimelineForMemory(memoryId: string) {
  return api.get<TimelineResponse>(`/memories/${memoryId}/timeline`);
}

export function listMemoryUsageEvents(memoryId?: string, traceRunId?: string) {
  const params: Record<string, string> = {};
  if (memoryId) params.memory_id = memoryId;
  if (traceRunId) params.trace_run_id = traceRunId;
  const qs = Object.keys(params).length ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<UsageEventsResponse>(`/memory-usage-events${qs}`);
}

export function listMemoryLifecycleEvents(memoryId?: string) {
  const params: Record<string, string> = {};
  if (memoryId) params.memory_id = memoryId;
  const qs = Object.keys(params).length ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<LifecycleEventsResponse>(`/memory-lifecycle-events${qs}`);
}
