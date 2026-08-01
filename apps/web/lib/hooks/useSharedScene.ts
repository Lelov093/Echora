"use client";

import { useCallback, useMemo } from "react";
import { usePaginatedData } from "./usePaginatedData";
import {
  createSharedScene,
  createSharedSceneEvent,
  getSharedScene,
  listSharedSceneEvents,
  listSharedScenes,
  patchSharedScene,
} from "@/lib/api/sharedScenes";
import type { SharedSceneBundle, SharedSceneEvent } from "@/lib/types";

export function useSharedScene(params?: Record<string, string | number | undefined | null>) {
  const paramsKey = JSON.stringify(params ?? {});
  const stableParams = useMemo(
    () => (paramsKey === "{}" ? undefined : (JSON.parse(paramsKey) as Record<string, string | number | undefined | null>)),
    [paramsKey],
  );
  const loadScenes = useCallback(
    () => listSharedScenes(stableParams),
    [stableParams],
  );
  const scenes = usePaginatedData<SharedSceneBundle>(loadScenes);
  return {
    ...scenes,
    create: createSharedScene,
    getById: getSharedScene,
    patch: patchSharedScene,
    listEvents: (sceneId: string) => listSharedSceneEvents(sceneId),
    createEvent: createSharedSceneEvent,
  };
}

export function useSharedSceneEvents(sceneId: string | null) {
  const loadEvents = useCallback(
    () => (sceneId ? listSharedSceneEvents(sceneId) : Promise.resolve({ items: [] })),
    [sceneId],
  );
  return usePaginatedData<SharedSceneEvent>(
    loadEvents,
    { enabled: Boolean(sceneId) },
  );
}
