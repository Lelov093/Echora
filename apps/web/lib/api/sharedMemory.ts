import { apiGet, apiPost } from "./client";
import type {
  CrossCompanionMemoryEvent,
  CrossCompanionMemoryReview,
  PaginatedItems,
  PrivateToSharedMemoryReview,
  SharedEpisodicMemory,
  SharedMemoryCandidate,
  SharedToPrivateMemoryReview,
} from "@/lib/types";

function toQuery(params?: Record<string, string | number | undefined | null>) {
  if (!params) return "";
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "");
  return entries.length > 0 ? `?${new URLSearchParams(entries.map(([key, value]) => [key, String(value)])).toString()}` : "";
}

export function listSharedMemories(params?: Record<string, string | number | undefined | null>) {
  return apiGet<PaginatedItems<SharedEpisodicMemory>>(`/shared-episodic-memories${toQuery(params)}`);
}

export function createSharedMemory(data: Record<string, unknown>) {
  return apiPost<SharedEpisodicMemory>("/shared-episodic-memories", data);
}

export function listSharedMemoryCandidates(params?: Record<string, string | number | undefined | null>) {
  return apiGet<PaginatedItems<SharedMemoryCandidate>>(`/shared-memory-candidates${toQuery(params)}`);
}

export function createSharedMemoryCandidate(data: Record<string, unknown>) {
  return apiPost<SharedMemoryCandidate>("/shared-memory-candidates", data);
}

export function decideSharedMemoryCandidate(candidateId: string, data: Record<string, unknown>) {
  return apiPost<{ candidate: SharedMemoryCandidate; shared_memory: SharedEpisodicMemory | null }>(
    `/shared-memory-candidates/${candidateId}/decision`,
    data,
  );
}

export function listPrivateToSharedReviews(params?: Record<string, string | number | undefined | null>) {
  return apiGet<PaginatedItems<PrivateToSharedMemoryReview>>(`/private-to-shared-memory-reviews${toQuery(params)}`);
}

export function decidePrivateToSharedReview(reviewId: string, data: Record<string, unknown>) {
  return apiPost<PrivateToSharedMemoryReview>(`/private-to-shared-memory-reviews/${reviewId}/decision`, data);
}

export function listSharedToPrivateReviews(params?: Record<string, string | number | undefined | null>) {
  return apiGet<PaginatedItems<SharedToPrivateMemoryReview>>(`/shared-to-private-memory-reviews${toQuery(params)}`);
}

export function decideSharedToPrivateReview(reviewId: string, data: Record<string, unknown>) {
  return apiPost<{ review: SharedToPrivateMemoryReview; memory: Record<string, unknown> | null }>(
    `/shared-to-private-memory-reviews/${reviewId}/decision`,
    data,
  );
}

export function listCrossCompanionReviews(params?: Record<string, string | number | undefined | null>) {
  return apiGet<PaginatedItems<CrossCompanionMemoryReview>>(`/cross-companion-memory-reviews${toQuery(params)}`);
}

export function createCrossCompanionReview(data: Record<string, unknown>) {
  return apiPost<CrossCompanionMemoryReview>("/cross-companion-memory-reviews", data);
}

export function decideCrossCompanionReview(reviewId: string, data: Record<string, unknown>) {
  return apiPost<{ review: CrossCompanionMemoryReview; event: CrossCompanionMemoryEvent }>(
    `/cross-companion-memory-reviews/${reviewId}/decision`,
    data,
  );
}
