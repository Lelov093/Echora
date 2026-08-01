import { api, queryString, type QueryParams } from "./client";
import type { LearningMode, PaginatedItems } from "@/lib/types";

export interface RerankerTrainingExample {
  id: string;
  memory_id?: string | null;
  feedback_event_id?: string | null;
  label: number;
  source_type: string;
  feature_json?: Record<string, unknown>;
}

export interface MemoryRerankerRun {
  id: string;
  trace_run_id?: string | null;
  learning_mode: LearningMode;
  status: string;
  candidate_memory_ids: string[];
  selected_memory_ids: string[];
  score_json?: Record<string, unknown>;
  explanation_json?: Record<string, unknown>;
}

export interface PresencePolicyFeedbackSample {
  id: string;
  presence_opportunity_id?: string | null;
  feedback_event_id?: string | null;
  action_taken: string;
  reward: number;
  feature_json?: Record<string, unknown>;
}

export interface PresencePolicyRun {
  id: string;
  trace_run_id?: string | null;
  presence_opportunity_id?: string | null;
  learning_mode: LearningMode;
  action_space: string[];
  selected_action: string;
  reward_prediction?: number | null;
  explanation_json?: Record<string, unknown>;
}

export function listRerankerTrainingExamples(params?: QueryParams) {
  return api.get<PaginatedItems<RerankerTrainingExample>>(`/reranker-training-examples${queryString(params)}`);
}
export function createRerankerTrainingExample(data: Partial<RerankerTrainingExample>) {
  return api.post<RerankerTrainingExample>("/reranker-training-examples", data);
}
export function createRerankerTrainingExampleFromFeedback(feedbackEventId: string, data?: Record<string, unknown>) {
  return api.post<RerankerTrainingExample>(`/reranker-training-examples/from-feedback/${feedbackEventId}`, data);
}
export function listMemoryRerankerRuns(params?: QueryParams) {
  return api.get<PaginatedItems<MemoryRerankerRun>>(`/memory-reranker-runs${queryString(params)}`);
}
export function createMemoryRerankerRun(data: Partial<MemoryRerankerRun> & { allow_active?: boolean }) {
  return api.post<MemoryRerankerRun>("/memory-reranker-runs", data);
}
export function listPresencePolicyFeedbackSamples(params?: QueryParams) {
  return api.get<PaginatedItems<PresencePolicyFeedbackSample>>(`/presence-policy-feedback-samples${queryString(params)}`);
}
export function createPresencePolicyFeedbackSample(data: Partial<PresencePolicyFeedbackSample>) {
  return api.post<PresencePolicyFeedbackSample>("/presence-policy-feedback-samples", data);
}
export function listPresencePolicyRuns(params?: QueryParams) {
  return api.get<PaginatedItems<PresencePolicyRun>>(`/presence-policy-runs${queryString(params)}`);
}
export function createPresencePolicyRun(data: Partial<PresencePolicyRun> & { allow_active?: boolean }) {
  return api.post<PresencePolicyRun>("/presence-policy-runs", data);
}
