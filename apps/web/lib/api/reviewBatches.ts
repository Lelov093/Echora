import { api } from "./client";

// Detail-level API client.
// Reserved for future review detail drawers.
// Do not remove: contract is validated by backend smoke tests.

export interface ReviewBatchItem {
  id?: string;
  item_type?: string;
  title?: string;
  status?: string;
  decision?: string;
}

export interface ReviewBatch {
  id: string;
  batch_type: string;
  title?: string | null;
  description?: string | null;
  item_count: number;
  accepted_count: number;
  edited_count: number;
  rejected_count: number;
  skipped_count: number;
  status: string;
  item_refs?: Array<Record<string, unknown>>;
  created_at?: string | null;
}

export function getReviewBatch(batchId: string) {
  return api.get<ReviewBatch>(`/review-batches/${batchId}`);
}

export function listReviewBatches(companionId?: string) {
  const params: Record<string, string> = {};
  if (companionId) params.companion_id = companionId;
  const qs = Object.keys(params).length ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<{ items: ReviewBatch[]; total: number }>(`/review-batches${qs}`);
}
