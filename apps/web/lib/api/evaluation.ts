import { api, queryString, type QueryParams } from "./client";
import type { EvaluationRun, PaginatedItems } from "@/lib/types";

export interface EvaluationDataset {
  id: string;
  name: string;
  description?: string | null;
  dataset_type: string;
  status: string;
}

export interface EvaluationCase {
  id: string;
  dataset_id?: string | null;
  case_type: string;
  title: string;
  input_json?: Record<string, unknown>;
  expected_behavior?: string | null;
  status: string;
}

export interface EvaluationResult {
  id: string;
  evaluation_run_id: string;
  evaluation_case_id?: string | null;
  status: string;
  score?: number | null;
  trace_run_id?: string | null;
  replay_id?: string | null;
  judge_reason?: string | null;
}

export function listEvaluationDatasets(params?: QueryParams) {
  return api.get<PaginatedItems<EvaluationDataset>>(`/evaluation-datasets${queryString(params)}`);
}
export function createEvaluationDataset(data: Partial<EvaluationDataset>) {
  return api.post<EvaluationDataset>("/evaluation-datasets", data);
}
export function listEvaluationCases(params?: QueryParams) {
  return api.get<PaginatedItems<EvaluationCase>>(`/evaluation-cases${queryString(params)}`);
}
export function createEvaluationCase(data: Partial<EvaluationCase>) {
  return api.post<EvaluationCase>("/evaluation-cases", data);
}
export function listEvaluationRuns(params?: QueryParams) {
  return api.get<PaginatedItems<EvaluationRun>>(`/evaluation-runs${queryString(params)}`);
}
export function createEvaluationRun(data: Partial<EvaluationRun>) {
  return api.post<EvaluationRun>("/evaluation-runs", data);
}
export function listEvaluationResults(params?: QueryParams) {
  return api.get<PaginatedItems<EvaluationResult>>(`/evaluation-results${queryString(params)}`);
}
export function createEvaluationResult(data: Partial<EvaluationResult>) {
  return api.post<EvaluationResult>("/evaluation-results", data);
}
export function createEvaluationResultBadCase(id: string, data?: Record<string, unknown>) {
  return api.post(`/evaluation-results/${id}/bad-case`, data);
}
