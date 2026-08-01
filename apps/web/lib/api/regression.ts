import { api, queryString, type QueryParams } from "./client";
import type { PaginatedItems, RegressionCase } from "@/lib/types";

export interface RegressionRun {
  id: string;
  status: string;
  total_count?: number;
  passed_count?: number;
  failed_count?: number;
  result_summary_json?: Record<string, unknown>;
}

export interface RegressionResult {
  id: string;
  regression_run_id: string;
  regression_case_id: string;
  status: string;
  score?: number | null;
  trace_run_id?: string | null;
  replay_id?: string | null;
  failure_reason?: string | null;
}

export function listRegressionCases(params?: QueryParams) {
  return api.get<PaginatedItems<RegressionCase>>(`/regression-cases${queryString(params)}`);
}
export function createRegressionCase(data: Partial<RegressionCase>) {
  return api.post<RegressionCase>("/regression-cases", data);
}
export function listRegressionRuns(params?: QueryParams) {
  return api.get<PaginatedItems<RegressionRun>>(`/regression-runs${queryString(params)}`);
}
export function createRegressionRun(data: Partial<RegressionRun>) {
  return api.post<RegressionRun>("/regression-runs", data);
}
export function listRegressionResults(params?: QueryParams) {
  return api.get<PaginatedItems<RegressionResult>>(`/regression-results${queryString(params)}`);
}
export function createRegressionResult(data: Partial<RegressionResult>) {
  return api.post<RegressionResult>("/regression-results", data);
}
export function createRegressionResultBadCase(id: string, data?: Record<string, unknown>) {
  return api.post(`/regression-results/${id}/bad-case`, data);
}
