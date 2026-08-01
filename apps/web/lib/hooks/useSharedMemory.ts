"use client";

import { useCallback, useMemo } from "react";
import { usePaginatedData } from "./usePaginatedData";
import {
  createCrossCompanionReview,
  createSharedMemory,
  createSharedMemoryCandidate,
  decideCrossCompanionReview,
  decidePrivateToSharedReview,
  decideSharedMemoryCandidate,
  decideSharedToPrivateReview,
  listCrossCompanionReviews,
  listPrivateToSharedReviews,
  listSharedMemories,
  listSharedMemoryCandidates,
  listSharedToPrivateReviews,
} from "@/lib/api/sharedMemory";
import type {
  CrossCompanionMemoryReview,
  PrivateToSharedMemoryReview,
  SharedEpisodicMemory,
  SharedMemoryCandidate,
  SharedToPrivateMemoryReview,
} from "@/lib/types";

export function useSharedMemory(params?: Record<string, string | number | undefined | null>) {
  const paramsKey = JSON.stringify(params ?? {});
  const stableParams = useMemo(
    () => (paramsKey === "{}" ? undefined : (JSON.parse(paramsKey) as Record<string, string | number | undefined | null>)),
    [paramsKey],
  );
  const loadMemories = useCallback(() => listSharedMemories(stableParams), [stableParams]);
  const loadCandidates = useCallback(() => listSharedMemoryCandidates(stableParams), [stableParams]);
  const loadCrossReviews = useCallback(() => listCrossCompanionReviews(stableParams), [stableParams]);
  const loadPrivateToShared = useCallback(() => listPrivateToSharedReviews(stableParams), [stableParams]);
  const loadSharedToPrivate = useCallback(() => listSharedToPrivateReviews(stableParams), [stableParams]);

  const memories = usePaginatedData<SharedEpisodicMemory>(loadMemories);
  const candidates = usePaginatedData<SharedMemoryCandidate>(loadCandidates);
  const crossReviews = usePaginatedData<CrossCompanionMemoryReview>(loadCrossReviews);
  const privateToShared = usePaginatedData<PrivateToSharedMemoryReview>(loadPrivateToShared);
  const sharedToPrivate = usePaginatedData<SharedToPrivateMemoryReview>(loadSharedToPrivate);

  const reloadAll = async () => {
    await Promise.all([
      memories.reload(),
      candidates.reload(),
      crossReviews.reload(),
      privateToShared.reload(),
      sharedToPrivate.reload(),
    ]);
  };

  return {
    memories,
    candidates,
    crossReviews,
    privateToShared,
    sharedToPrivate,
    reloadAll,
    createSharedMemory,
    createSharedMemoryCandidate,
    decideSharedMemoryCandidate,
    createCrossCompanionReview,
    decideCrossCompanionReview,
    decidePrivateToSharedReview,
    decideSharedToPrivateReview,
  };
}
