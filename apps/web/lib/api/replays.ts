import { api, queryString, type QueryParams } from "./client";
import type { AgentRunReplay, PaginatedItems } from "@/lib/types";

export interface ReplayAnnotation {
  id: string;
  agent_run_replay_id: string;
  annotation_type: string;
  target_ref_json?: Record<string, unknown>;
  content: string;
}

export function listReplays(params?: QueryParams) {
  return api.get<PaginatedItems<AgentRunReplay>>(`/replays${queryString(params)}`);
}
export function createReplayFromTrace(traceRunId: string, data?: Record<string, unknown>) {
  return api.post<AgentRunReplay>(`/replays/from-trace/${traceRunId}`, data);
}
export function getReplay(id: string) {
  return api.get<AgentRunReplay>(`/replays/${id}`);
}
export function createReplayAnnotation(id: string, data: Partial<ReplayAnnotation>) {
  return api.post<ReplayAnnotation>(`/replays/${id}/annotations`, data);
}
export function createReplayBadCase(id: string, data?: Record<string, unknown>) {
  return api.post(`/replays/${id}/bad-case`, data);
}
export function createReplayRegressionCase(id: string, data?: Record<string, unknown>) {
  return api.post(`/replays/${id}/regression-case`, data);
}
