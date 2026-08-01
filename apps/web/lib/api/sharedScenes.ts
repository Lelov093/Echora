import { apiGet, apiPatch, apiPost } from "./client";
import type { PaginatedItems, SharedSceneBundle, SharedSceneEvent, SharedExperienceRecord } from "@/lib/types";

function toQuery(params?: Record<string, string | number | undefined | null>) {
  if (!params) return "";
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "");
  return entries.length > 0 ? `?${new URLSearchParams(entries.map(([key, value]) => [key, String(value)])).toString()}` : "";
}

export function listSharedScenes(params?: Record<string, string | number | undefined | null>) {
  return apiGet<PaginatedItems<SharedSceneBundle>>(`/shared-scenes${toQuery(params)}`);
}

export function createSharedScene(data: Record<string, unknown>) {
  return apiPost<SharedSceneBundle>("/shared-scenes", data);
}

export function getSharedScene(sceneId: string) {
  return apiGet<SharedSceneBundle>(`/shared-scenes/${sceneId}`);
}

export function patchSharedScene(sceneId: string, data: Record<string, unknown>) {
  return apiPatch<SharedSceneBundle>(`/shared-scenes/${sceneId}`, data);
}

export function listSharedSceneEvents(sceneId: string) {
  return apiGet<{ items: SharedSceneEvent[] }>(`/shared-scenes/${sceneId}/events`);
}

export function createSharedSceneEvent(sceneId: string, data: Record<string, unknown>) {
  return apiPost<{ event: SharedSceneEvent; shared_experience: SharedExperienceRecord | null }>(
    `/shared-scenes/${sceneId}/events`,
    data,
  );
}
